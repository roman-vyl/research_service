from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from test_experiments_api import RATIO_SCHEMA, TRAIL_SCHEMA
from test_runs_bff import _container, _persist

from research_service.api.app import create_app
from research_service.runtime.settings import Settings

URL = "/api/research/candidates"
RATIO_HEADER = [
    "min_current_width_atr", "untouched_lookback", "sl_atr_multiplier",
    "return_pct", "profit_factor", "run_id", "market_data_hash",
]
TRAIL_HEADER = ["w", "sl", "grid", "t_atr", "t_r", "arm", "net", "run_id", "source"]


def _write(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _setup(tmp_path: Path) -> tuple[TestClient, list[str], Path]:
    runs = tmp_path / "runs"
    runs.mkdir()
    ids = [_persist(runs, f"2026-01-0{i + 1}T00:00:00+00:00") for i in range(2)]
    analysis = tmp_path / "analysis"
    ratio = analysis / "BTC" / "ratio"
    trail = analysis / "BTC" / "trail"
    ratio.mkdir(parents=True)
    trail.mkdir(parents=True)
    _write(
        ratio / "runs.csv",
        RATIO_HEADER,
        [[3, 20, 6.0, "0.25", "1.5", ids[0], "h1"],
         [3, 30, 6.0, "-0.1", "0.9", ids[1], "h2"],
         [4, 20, 6.0, "0.5", "2.0", "", "h3"],
         [5, 20, 6.0, "0.1", "1.1", "", "h4"],
         [5, 20, 6.0, "0.2", "1.2", "", "h5"]],
    )
    manifest = {
        "experiment_id": "btc.ema500.ratio",
        "varied_params": [
            {"column": "min_current_width_atr", "label": "Stack width",
             "component_id": "anchor_stack_width_setup", "component_param": "min_current_width_atr"},
        ],
        "fixed_params": {"initial_equity": 10000, "entry_fee_rate": 0.0004},
        "result_schema": RATIO_SCHEMA,
    }
    (ratio / "manifest.json").write_text(json.dumps(manifest))
    _write(
        trail / "runs.csv",
        TRAIL_HEADER,
        [[3, 5, "R", 35, 7, "trail", 100.5, "", "replay"],
         [3, 5, "ATR", 10, 2, "trail", 7, "", "replay"],
         [3, 5, "", "", "", "ctl", 40, "", "replay"]],
    )
    (trail / "manifest.json").write_text(json.dumps({"result_schema": TRAIL_SCHEMA}))
    (analysis / "experiments.json").write_text(
        json.dumps(
            {
                "registry_version": 1,
                "experiments": [
                    {"experiment_id": "btc.ema500.ratio", "title": "Ratio", "ticker": "BTC",
                     "anchor": "EMA500", "manifest": "BTC/ratio/manifest.json"},
                    {"experiment_id": "btc.ema500.trail", "title": "Trail", "ticker": "BTC",
                     "anchor": "EMA500", "manifest": "BTC/trail/manifest.json"},
                ],
            }
        )
    )
    settings = Settings(artifacts_root=runs, configs_root=tmp_path / "configs")
    return TestClient(create_app(settings, _container(runs))), ids, ratio


def _star(client: TestClient, coords: dict[str, object], experiment: str = "btc.ema500.ratio") -> dict:
    resp = client.put(URL, json={"experiment_id": experiment, "coords": coords})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def _listed(client: TestClient) -> list[dict]:
    resp = client.get(URL)
    assert resp.status_code == 200, resp.text
    return resp.json()["candidates"]  # type: ignore[no-any-return]


def _rewrite(path: Path, edit: object) -> None:
    with path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    edit(rows)  # type: ignore[operator]
    with path.open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)


def test_star_snapshot_spec_and_idempotent_id(tmp_path: Path) -> None:
    client, ids, ratio = _setup(tmp_path)
    first = _star(client, {"width": 3, "lookback": 20, "sl": 6})
    again = _star(client, {"width": "3.0", "lookback": 20.0, "sl": "6.000"})
    assert again == first
    assert first["candidate_id"].startswith("cand_")
    assert first["coords"] == {"width": "3", "lookback": "20", "sl": "6"}
    assert "status" not in first
    assert first["snapshot"] == {
        "metrics": {"return_pct": 0.25, "profit_factor": 1.5},
        "provenance": "engine",
        "run_id": ids[0],
        "row_columns": {"market_data_hash": "h1"},
    }
    assert "run_id" not in first["fingerprint_fields"]
    assert "provenance" not in first["fingerprint_fields"]
    spec = first["strategy_spec_snapshot"]
    assert spec["source"] == "run_request" and spec["run_id"] == ids[0] and "raw_spec" in spec["spec"]
    stored = json.loads((tmp_path / "analysis" / "candidates.json").read_text())
    assert stored["contract_version"] == "research_candidates.v1" and len(stored["candidates"]) == 1
    journal = (tmp_path / "analysis" / "candidates_journal.jsonl").read_text().splitlines()
    assert [json.loads(line)["action"] for line in journal] == ["star"]
    assert (ratio / "runs.csv").read_text().count("\n") == 6  # table untouched


def test_listing_same_with_meaning(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    _star(client, {"width": 3, "lookback": 20, "sl": 6})
    [listed] = _listed(client)
    current = listed["current"]
    assert current["row_state"] == "same" and current["run_id"] == ids[0]
    assert current["provenance"] == "engine"
    assert current["metrics"] == {"return_pct": 0.25, "profit_factor": 1.5}
    meaning = current["meaning"]
    assert meaning["title"] == "Ratio" and meaning["anchor"] == "EMA500"
    assert meaning["fixed_params"] == {"initial_equity": 10000, "entry_fee_rate": 0.0004}
    width = meaning["coords"][0]
    assert width == {"id": "width", "label": "Stack width", "value": "3", "unit": "ATR",
                     "component_id": "anchor_stack_width_setup",
                     "component_param": "min_current_width_atr"}


def test_unstar_removes_and_journals(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    record = _star(client, {"width": 3, "lookback": 20, "sl": 6})
    resp = client.delete(f"{URL}/{record['candidate_id']}")
    assert resp.json() == {"removed": True}
    assert _listed(client) == []
    assert client.delete(f"{URL}/{record['candidate_id']}").json() == {"removed": False}
    journal = (tmp_path / "analysis" / "candidates_journal.jsonl").read_text().splitlines()
    assert [json.loads(line)["action"] for line in journal] == ["star", "unstar"]


def test_run_deleted_stays_same_without_run(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    record = _star(client, {"width": 3, "lookback": 20, "sl": 6})
    base = "/api/research/experiments/btc.ema500.ratio/runs"
    plan = client.post(f"{base}/delete-plan", json={"run_ids": [ids[0]]}).json()
    assert client.post(
        f"{base}/delete", json={"run_ids": [ids[0]], "plan_token": plan["plan_token"]}
    ).status_code == 200
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "same" and listed["current"]["run_id"] is None
    assert listed["candidate_id"] == record["candidate_id"]
    assert listed["strategy_spec_snapshot"]["run_id"] == ids[0]


def test_provenance_change_alone_is_same(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    _star(client, {"width": 3, "sl": 5, "grid": "R", "trigger": 7, "arm": "trail"}, "btc.ema500.trail")
    trail = tmp_path / "analysis" / "BTC" / "trail" / "runs.csv"

    def to_engine(rows: list[list[str]]) -> None:
        rows[1][7] = "run_" + "e" * 32
        rows[1][8] = "engine"

    _rewrite(trail, to_engine)
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "same"
    assert listed["current"]["provenance"] == "engine"
    assert listed["current"]["run_id"] == "run_" + "e" * 32


def test_metric_change_is_changed_with_snapshot_kept(tmp_path: Path) -> None:
    client, _, ratio = _setup(tmp_path)
    _star(client, {"width": 4, "lookback": 20, "sl": 6})

    def bump(rows: list[list[str]]) -> None:
        rows[3][3] = "0.55"

    _rewrite(ratio / "runs.csv", bump)
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "changed"
    assert listed["current"]["metrics"]["return_pct"] == 0.55
    assert listed["snapshot"]["metrics"]["return_pct"] == 0.5


def test_number_formatting_and_auxiliary_columns_keep_same(tmp_path: Path) -> None:
    client, _, ratio = _setup(tmp_path)
    _star(client, {"width": 4, "lookback": 20, "sl": 6})

    def reformat(rows: list[list[str]]) -> None:
        rows[0].append("extra")
        for row in rows[1:]:
            row.append("x")
        rows[3][3] = "0.50000"
        rows[3][2] = "6"

    _rewrite(ratio / "runs.csv", reformat)
    manifest_path = ratio / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["result_schema"]["metrics"].append({"column": "extra", "label": "E", "format": "number"})
    manifest_path.write_text(json.dumps(manifest))

    def numeric_extra(rows: list[list[str]]) -> None:
        for row in rows[1:]:
            row[-1] = "1"

    _rewrite(ratio / "runs.csv", numeric_extra)
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "same"


def test_missing_row_and_unregistered_experiment(tmp_path: Path) -> None:
    client, _, ratio = _setup(tmp_path)
    _star(client, {"width": 4, "lookback": 20, "sl": 6})
    _rewrite(ratio / "runs.csv", lambda rows: rows.pop(3))
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "missing"
    assert listed["snapshot"]["metrics"]["return_pct"] == 0.5
    registry_path = tmp_path / "analysis" / "experiments.json"
    registry = json.loads(registry_path.read_text())
    registry["experiments"] = registry["experiments"][1:]
    registry_path.write_text(json.dumps(registry))
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "missing" and listed["current"]["meaning"] is None


def test_ambiguous_rows(tmp_path: Path) -> None:
    client, _, ratio = _setup(tmp_path)
    resp = client.put(URL, json={"experiment_id": "btc.ema500.ratio",
                                 "coords": {"width": 5, "lookback": 20, "sl": 6}})
    assert resp.status_code == 409 and resp.json()["error"] == "ambiguous_row"
    assert not (tmp_path / "analysis" / "candidates.json").exists()
    _star(client, {"width": 4, "lookback": 20, "sl": 6})

    def duplicate(rows: list[list[str]]) -> None:
        rows.append(list(rows[3]))

    _rewrite(ratio / "runs.csv", duplicate)
    [listed] = _listed(client)
    assert listed["current"]["row_state"] == "ambiguous"


def test_errors_on_star(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    cases = [
        ({"width": 3, "lookback": 20}, 400, "invalid_coords"),
        ({"width": 3, "lookback": 20, "sl": 6, "tp": 1}, 400, "invalid_coords"),
        ({"width": "x", "lookback": 20, "sl": 6}, 400, "invalid_coords"),
        ({"width": 9, "lookback": 20, "sl": 6}, 404, "row_not_found"),
    ]
    for coords, status, error in cases:
        resp = client.put(URL, json={"experiment_id": "btc.ema500.ratio", "coords": coords})
        assert resp.status_code == status and resp.json()["error"] == error, resp.text
    unknown = client.put(URL, json={"experiment_id": "nope", "coords": {}})
    assert unknown.status_code == 404 and unknown.json()["error"] == "experiment_not_found"


def test_replay_point_multi_grid_and_arm(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    treat = _star(client, {"width": 3, "sl": 5, "grid": "R", "trigger": 7, "arm": "trail"},
                  "btc.ema500.trail")
    assert treat["strategy_spec_snapshot"] is None
    assert treat["snapshot"]["provenance"] == "replay" and treat["snapshot"]["run_id"] is None
    assert treat["snapshot"]["metrics"] == {"net": 100.5}
    atr = _star(client, {"width": 3, "sl": 5, "grid": "ATR", "trigger": 10, "arm": "trail"},
                "btc.ema500.trail")
    assert atr["snapshot"]["metrics"] == {"net": 7}
    ctl = _star(client, {"width": 3, "sl": 5, "grid": None, "trigger": None, "arm": "ctl"},
                "btc.ema500.trail")
    assert ctl["snapshot"]["metrics"] == {"net": 40}
    assert len({treat["candidate_id"], atr["candidate_id"], ctl["candidate_id"]}) == 3
    listed = _listed(client)
    assert [c["current"]["row_state"] for c in listed] == ["same", "same", "same"]
    units = {c["id"]: c["unit"] for c in listed[0]["current"]["meaning"]["coords"]}
    assert units["trigger"] == "R"


def test_unreadable_request_json_does_not_fail_star(tmp_path: Path) -> None:
    client, ids, _ = _setup(tmp_path)
    (tmp_path / "runs" / ids[1] / "request.json").write_text("{not json")
    record = _star(client, {"width": 3, "lookback": 30, "sl": 6})
    spec = record["strategy_spec_snapshot"]
    assert spec["source"] is None and spec["run_id"] == ids[1] and "request.json" in spec["reason"]


def test_unreadable_candidates_file_is_not_overwritten(tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    path = tmp_path / "analysis" / "candidates.json"
    path.write_text("garbage")
    assert client.get(URL).status_code == 500
    resp = client.put(URL, json={"experiment_id": "btc.ema500.ratio",
                                 "coords": {"width": 3, "lookback": 20, "sl": 6}})
    assert resp.status_code == 500 and resp.json()["error"] == "invalid_candidates_file"
    assert path.read_text() == "garbage"


def test_shortlist_never_lists_runs(tmp_path: Path) -> None:
    client, _, ratio = _setup(tmp_path)
    with mock.patch("os.listdir", side_effect=AssertionError("listed")), \
            mock.patch("os.scandir", side_effect=AssertionError("listed")), \
            mock.patch.object(Path, "iterdir", side_effect=AssertionError("listed")):
        _star(client, {"width": 3, "lookback": 20, "sl": 6})
        _rewrite(ratio / "runs.csv", lambda rows: rows[1].__setitem__(4, "1.6"))
        assert _listed(client)[0]["current"]["row_state"] == "changed"
