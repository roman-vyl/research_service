from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi.testclient import TestClient
from test_experiments_api import RATIO_SCHEMA
from test_runs_bff import _container, _persist

from research_service.api.app import create_app
from research_service.runtime.settings import Settings

HEADER = [
    "min_current_width_atr", "untouched_lookback", "sl_atr_multiplier",
    "return_pct", "profit_factor", "run_id", "market_data_hash",
]
BASE = "/api/research/experiments/btc.ema500.ratio"


def _setup(tmp_path: Path) -> tuple[TestClient, list[str], Path]:
    runs = tmp_path / "runs"
    runs.mkdir()
    ids = [_persist(runs, f"2026-01-0{i + 1}T00:00:00+00:00") for i in range(4)]
    analysis = tmp_path / "analysis"
    ratio = analysis / "BTC" / "ratio"
    other = analysis / "BTC" / "other"
    ratio.mkdir(parents=True)
    other.mkdir(parents=True)
    # Quoted cell and CRLF on purpose: untouched cells must survive the rewrite.
    rows = [
        [3, 20, 3.0, "0.25", "1.5", ids[0], "h1"],
        [3, 30, 4.0, "-0.1", "0.9", ids[1], 'h,"2"'],
        [4, 20, 3.0, "0.5", "2.0", ids[2], "h3"],
        [5, 20, 3.0, "0.1", "1.1", "", "h4"],
    ]
    with (ratio / "runs.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)
    with (other / "runs.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerow([9, 9, 9.0, "0", "0", ids[2], "x"])
        w.writerow([9, 9, 9.0, "0", "0", ids[3], "x"])
    (ratio / "manifest.json").write_text(
        json.dumps({"experiment_id": "btc.ema500.ratio", "result_schema": RATIO_SCHEMA})
    )
    (other / "manifest.json").write_text(
        json.dumps({"experiment_id": "btc.ema500.other", "result_schema": RATIO_SCHEMA})
    )
    (analysis / "experiments.json").write_text(
        json.dumps(
            {
                "registry_version": 1,
                "experiments": [
                    {"experiment_id": "btc.ema500.ratio", "title": "R", "ticker": "BTC",
                     "anchor": "EMA500", "manifest": "BTC/ratio/manifest.json"},
                    {"experiment_id": "btc.ema500.other", "title": "O", "ticker": "BTC",
                     "anchor": "EMA500", "manifest": "BTC/other/manifest.json"},
                ],
            }
        )
    )
    settings = Settings(artifacts_root=runs, configs_root=tmp_path / "configs")
    client = TestClient(create_app(settings, _container(runs)))
    return client, ids, ratio


def _cells(path: Path) -> list[list[str]]:
    with path.open(newline="") as fh:
        return list(csv.reader(fh))


def _plan(client: TestClient, run_ids: list[str]) -> dict:
    resp = client.post(f"{BASE}/runs/delete-plan", json={"run_ids": run_ids})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def test_plan_counts_and_changes_nothing(tmp_path: Path) -> None:
    client, ids, ratio = _setup(tmp_path)
    before = (ratio / "runs.csv").read_bytes()
    plan = _plan(client, [ids[0], ids[1]])
    assert plan["run_count"] == 2 and plan["already_absent"] == 0 and plan["skipped"] == []
    on_disk = [p for i in ids[:2] for p in (tmp_path / "runs" / i).rglob("*") if p.is_file()]
    assert plan["file_count"] == len(on_disk) and plan["bytes"] == sum(p.stat().st_size for p in on_disk)
    assert plan["plan_token"].startswith("sha256:")
    assert (ratio / "runs.csv").read_bytes() == before
    assert all((tmp_path / "runs" / i).is_dir() for i in ids)
    assert not list(ratio.glob("*.pre_delete_*")) and not (ratio / "runs_deleted.jsonl").exists()


def test_skipped_reasons(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    plan = _plan(client, [ids[0], ids[2], ids[3], "run_" + "f" * 32, "not-a-run"])
    assert plan["run_count"] == 1
    reasons = {s["run_id"]: s["reason"] for s in plan["skipped"]}
    assert reasons == {
        ids[2]: "shared_with_other_experiment",
        ids[3]: "not_in_experiment",
        "run_" + "f" * 32: "not_in_experiment",
        "not-a-run": "invalid_run_id",
    }


def test_delete_clears_run_id_and_keeps_everything_else(tmp_path: Path) -> None:
    client, ids, ratio = _setup(tmp_path)
    before_bytes = (ratio / "runs.csv").read_bytes()
    before = _cells(ratio / "runs.csv")
    results_before = client.get(f"{BASE}/results").json()
    plan = _plan(client, [ids[0], ids[1]])
    resp = client.post(
        f"{BASE}/runs/delete", json={"run_ids": [ids[0], ids[1]], "plan_token": plan["plan_token"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted"] == 2 and body["cleared_rows"] == 2 and body["bytes"] == plan["bytes"]

    after = _cells(ratio / "runs.csv")
    expected = [list(r) for r in before]
    run_col = HEADER.index("run_id")
    for row in expected[1:]:
        if row[run_col] in {ids[0], ids[1]}:
            row[run_col] = ""
    assert after == expected
    assert b"\r\n" in (ratio / "runs.csv").read_bytes()
    # backup is the table as it was; journal line written
    assert (ratio / body["backup"]).read_bytes() == before_bytes
    journal = [json.loads(x) for x in (ratio / "runs_deleted.jsonl").read_text().splitlines()]
    assert journal[0]["run_ids"] == sorted([ids[0], ids[1]]) and journal[0]["backup"] == body["backup"]
    assert not list(ratio.glob("runs.csv.tmp-*"))
    # folders gone, others untouched
    assert not (tmp_path / "runs" / ids[0]).exists() and not (tmp_path / "runs" / ids[1]).exists()
    assert (tmp_path / "runs" / ids[2]).is_dir() and (tmp_path / "runs" / ids[3]).is_dir()
    # Surface values unchanged: only the run_id column differs
    results_after = client.get(f"{BASE}/results").json()
    ci = results_before["columns"].index("run_id")
    for c, (b, a) in enumerate(zip(results_before["data"], results_after["data"], strict=True)):
        if c != ci:
            assert a == b
    assert results_after["data"][ci][:2] == [None, None]


def test_run_list_stays_valid_and_deleted_run_is_404(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    plan = _plan(client, [ids[0]])
    client.post(f"{BASE}/runs/delete", json={"run_ids": [ids[0]], "plan_token": plan["plan_token"]})
    listed = client.get("/api/research/runs")
    assert listed.status_code == 200
    assert {r["run_id"] for r in listed.json()} == set(ids[1:])
    gone = client.get(f"/api/research/runs/{ids[0]}")
    assert gone.status_code == 404 and gone.json()["error"] == "run_not_found"


def test_stale_token_after_table_or_selection_change(tmp_path: Path) -> None:
    client, ids, ratio = _setup(tmp_path)
    plan = _plan(client, [ids[0]])
    # different selection
    r = client.post(f"{BASE}/runs/delete", json={"run_ids": [ids[1]], "plan_token": plan["plan_token"]})
    assert r.status_code == 409 and r.json()["error"] == "plan_stale"
    # table changed after the plan
    with (ratio / "runs.csv").open("a", newline="") as fh:
        fh.write("6,20,3.0,0,0,,h9\r\n")
    r = client.post(f"{BASE}/runs/delete", json={"run_ids": [ids[0]], "plan_token": plan["plan_token"]})
    assert r.status_code == 409 and r.json()["error"] == "plan_stale"
    assert all((tmp_path / "runs" / i).is_dir() for i in ids)
    assert not list(ratio.glob("*.pre_delete_*"))


def test_repeat_after_partial_removal_completes(tmp_path: Path) -> None:
    client, ids, ratio = _setup(tmp_path)
    import shutil

    shutil.rmtree(tmp_path / "runs" / ids[0])  # a previous run stopped after removing a folder
    plan = _plan(client, [ids[0], ids[1]])
    assert plan["run_count"] == 2 and plan["already_absent"] == 1
    body = client.post(
        f"{BASE}/runs/delete", json={"run_ids": [ids[0], ids[1]], "plan_token": plan["plan_token"]}
    ).json()
    assert body["deleted"] == 1 and body["already_absent"] == 1 and body["cleared_rows"] == 2
    run_col = HEADER.index("run_id")
    assert [r[run_col] for r in _cells(ratio / "runs.csv")[1:]] == ["", "", ids[2], ""]
    again = _plan(client, [ids[0], ids[1]])
    assert again["run_count"] == 0
    assert {s["reason"] for s in again["skipped"]} == {"not_in_experiment"}


def test_symlinked_run_folder_is_skipped(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    real = tmp_path / "elsewhere"
    (tmp_path / "runs" / ids[0]).rename(real)
    (tmp_path / "runs" / ids[0]).symlink_to(real, target_is_directory=True)
    plan = _plan(client, [ids[0]])
    assert plan["run_count"] == 0 and plan["skipped"] == [{"run_id": ids[0], "reason": "not_a_directory"}]


def test_errors_unknown_experiment_and_empty_selection(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    r = client.post("/api/research/experiments/nope/runs/delete-plan", json={"run_ids": ["x"]})
    assert r.status_code == 404 and r.json()["error"] == "experiment_not_found"
    r = client.post(f"{BASE}/runs/delete-plan", json={"run_ids": []})
    assert r.status_code == 400
    r = client.post(f"{BASE}/runs/delete", json={"run_ids": ["x"]})
    assert r.status_code == 422


def test_read_routes_are_unchanged(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    assert client.get("/api/research/experiments").status_code == 200
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/runs/delete-plan").status_code == 405
