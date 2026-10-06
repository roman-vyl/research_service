from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_experiments_api import RATIO_SCHEMA
from test_run_deletion import HEADER
from test_runs_bff import _container, _persist

from research_service.adapters.experiments import storage as storage_module
from research_service.api.app import create_app
from research_service.runtime.settings import Settings

BASE = "/api/research/experiments/btc.ema500.ratio"
OTHER = "/api/research/experiments/btc.ema500.other"


def _write(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)


def _tree_bytes(folder: Path) -> int:
    return sum(os.lstat(os.path.join(r, n)).st_size for r, _d, ns in os.walk(folder) for n in ns)


def _setup(tmp_path: Path) -> tuple[TestClient, list[str], Path, Path]:
    runs = tmp_path / "runs"
    runs.mkdir()
    ids = [_persist(runs, f"2026-01-0{i + 1}T00:00:00+00:00") for i in range(3)]
    analysis = tmp_path / "analysis"
    ratio = analysis / "BTC" / "ratio"
    other = analysis / "BTC" / "other"
    ratio.mkdir(parents=True)
    other.mkdir(parents=True)
    missing = "run_" + "f" * 32
    _write(ratio / "runs.csv", [
        [3, 20, 3.0, "0.25", "1.5", ids[0], "h1"],
        [3, 30, 3.0, "0.1", "1.1", ids[0], "h2"],
        [4, 20, 3.0, "0.5", "2.0", ids[1], "h3"],
        [4, 30, 3.0, "0.2", "1.2", missing, "h4"],
        [5, 20, 3.0, "0.1", "1.1", "", "h5"],
    ])
    _write(other / "runs.csv", [[9, 9, 9.0, "0", "0", ids[1], "x"]])
    for folder, eid in ((ratio, "btc.ema500.ratio"), (other, "btc.ema500.other")):
        (folder / "manifest.json").write_text(json.dumps({"experiment_id": eid, "result_schema": RATIO_SCHEMA}))
    (analysis / "experiments.json").write_text(json.dumps({
        "registry_version": 1,
        "experiments": [
            {"experiment_id": "btc.ema500.ratio", "title": "R", "ticker": "BTC", "anchor": "EMA500",
             "manifest": "BTC/ratio/manifest.json"},
            {"experiment_id": "btc.ema500.other", "title": "O", "ticker": "BTC", "anchor": "EMA500",
             "manifest": "BTC/other/manifest.json"},
        ],
    }))
    settings = Settings(artifacts_root=runs, configs_root=tmp_path / "configs")
    client = TestClient(create_app(settings, _container(runs)))
    return client, ids, runs, ratio


def _get(client: TestClient, url: str) -> dict:
    resp = client.get(url)
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    out = {}
    for r, _d, ns in os.walk(root):
        for n in ns:
            st = os.lstat(os.path.join(r, n))
            out[os.path.join(r, n)] = (st.st_size, st.st_mtime_ns)
    return out


def test_counts_and_cached_before_compute_reads_no_run_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ids, _runs, _ratio = _setup(tmp_path)
    walked: list[Path] = []
    real = storage_module._folder_size
    monkeypatch.setattr(storage_module, "_folder_size", lambda p: (walked.append(p), real(p))[1])
    body = _get(client, f"{BASE}/storage")
    assert body == {
        "experiment_id": "btc.ema500.ratio", "rows": 5, "engine_runs": 4, "distinct_run_ids": 3, "size": None,
    }
    assert _get(client, f"{BASE}/storage?size=cached")["size"] is None
    assert walked == []


def test_compute_sizes_missing_runs_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, ids, runs, ratio = _setup(tmp_path)
    size = _get(client, f"{BASE}/storage?size=compute")["size"]
    run_bytes = _tree_bytes(runs / ids[0]) + _tree_bytes(runs / ids[1])
    assert size["run_bytes"] == run_bytes
    assert size["experiment_folder_bytes"] == _tree_bytes(ratio)
    assert size["bytes"] == run_bytes + _tree_bytes(ratio)
    assert size["missing_runs"] == 1
    assert size["computed_at"].endswith("Z")

    def fail(_p: Path) -> tuple[int, int]:
        raise AssertionError("cache miss")

    monkeypatch.setattr(storage_module, "_folder_size", fail)
    assert _get(client, f"{BASE}/storage?size=cached")["size"] == size
    assert _get(client, f"{BASE}/storage?size=compute")["size"] == size


def test_shared_run_counts_in_both(tmp_path: Path) -> None:
    client, ids, runs, _ratio = _setup(tmp_path)
    other = _get(client, f"{OTHER}/storage?size=compute")["size"]
    assert other["run_bytes"] == _tree_bytes(runs / ids[1])


def test_invalid_id_and_symlink_are_missing_and_not_followed(tmp_path: Path) -> None:
    client, ids, runs, ratio = _setup(tmp_path)
    link = "run_" + "a" * 32
    os.symlink(runs / ids[2], runs / link)
    _write(ratio / "runs.csv", [
        [3, 20, 3.0, "0", "0", "../runs", "h"],
        [3, 30, 3.0, "0", "0", link, "h"],
        [4, 20, 3.0, "0", "0", ids[0], "h"],
    ])
    size = _get(client, f"{BASE}/storage?size=compute")["size"]
    assert size["missing_runs"] == 2
    assert size["run_bytes"] == _tree_bytes(runs / ids[0])


def test_table_rewrite_misses_the_cache(tmp_path: Path) -> None:
    client, ids, _runs, _ratio = _setup(tmp_path)
    assert _get(client, f"{BASE}/storage?size=compute")["size"] is not None
    plan = client.post(f"{BASE}/runs/delete-plan", json={"run_ids": [ids[0]]}).json()
    resp = client.post(f"{BASE}/runs/delete", json={"run_ids": [ids[0]], "plan_token": plan["plan_token"]})
    assert resp.status_code == 200, resp.text
    body = _get(client, f"{BASE}/storage?size=cached")
    assert body["size"] is None
    assert body["engine_runs"] == 2
    assert body["distinct_run_ids"] == 2


def test_errors_and_no_write(tmp_path: Path) -> None:
    client, _ids, _runs, _ratio = _setup(tmp_path)
    before = _snapshot(tmp_path)
    assert client.get("/api/research/experiments/nope/storage").status_code == 404
    assert client.get(f"{BASE}/storage?size=all").status_code == 422
    _get(client, f"{BASE}/storage?size=compute")
    assert _snapshot(tmp_path) == before
