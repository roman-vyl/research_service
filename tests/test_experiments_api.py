from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi.testclient import TestClient
from test_runs_bff import _container

from research_service.api.app import create_app
from research_service.runtime.settings import Settings

RATIO_SCHEMA = {
    "contract_version": "research_experiment_result_schema.v1",
    "table": "runs.csv",
    "run_id_column": "run_id",
    "provenance": {"value": "engine"},
    "row_columns": {"market_data_hash": "market_data_hash"},
    "dimensions": [
        {"id": "width", "column": "min_current_width_atr", "unit": "ATR"},
        {"id": "lookback", "column": "untouched_lookback", "unit": "bars"},
        {"id": "sl", "column": "sl_atr_multiplier", "unit": "ATR"},
    ],
    "metrics": [
        {"column": "return_pct", "label": "Return", "format": "fraction"},
        {"column": "profit_factor", "label": "PF", "format": "number"},
    ],
    "view": [
        {"id": "main", "x": "lookback", "y": "width", "controls": ["sl"], "default_metric": "return_pct"}
    ],
}

TRAIL_SCHEMA = {
    "contract_version": "research_experiment_result_schema.v1",
    "table": "runs.csv",
    "run_id_column": "run_id",
    "provenance": {"column": "source"},
    "dimensions": [
        {"id": "width", "column": "w", "unit": "ATR"},
        {"id": "sl", "column": "sl", "unit": "ATR"},
        {
            "id": "trigger",
            "grid_column": "grid",
            "grids": {
                "ATR": {"column": "t_atr", "unit": "ATR"},
                "R": {"column": "t_r", "unit": "R"},
            },
        },
    ],
    "arms": {
        "column": "arm",
        "roles": {"trail": "treatment", "ctl": "comparison"},
        "baseline": "ctl",
        "match_on": ["width", "sl"],
    },
    "metrics": [{"column": "net", "label": "Net", "format": "number", "unit": "USDT"}],
    "view": [
        {"id": "v", "x": "width", "y": "sl", "controls": ["grid", "trigger"], "default_metric": "net"}
    ],
}


def _write(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _client(tmp_path: Path, *, registry: bool = True) -> TestClient:
    analysis = tmp_path / "analysis"
    ratio = analysis / "BTC" / "ema500" / "ratio"
    trail = analysis / "BTC" / "ema500" / "trail"
    _write(
        ratio / "runs.csv",
        ["min_current_width_atr", "untouched_lookback", "sl_atr_multiplier", "return_pct",
         "profit_factor", "run_id", "market_data_hash"],
        [[3, 20, 3.0, "0.25", "1.5", "run_" + "a" * 32, "h1"],
         [3, 30, 4.0, "-0.1", "0.9", "run_" + "b" * 32, "h2"]],
    )
    (ratio / "manifest.json").write_text(
        json.dumps({"test_id": "ratio_4d", "experiment_id": "btc.ema500.ratio", "result_schema": RATIO_SCHEMA})
    )
    _write(
        trail / "runs.csv",
        ["w", "sl", "grid", "t_atr", "t_r", "arm", "net", "run_id", "source"],
        [[3, 5, "R", 35, 7, "trail", 100.5, "run_" + "c" * 32, "replay"],
         [3, 5, "ATR", 10, 2, "trail", 7, "", "replay"],
         [3, 5, "", "", "", "ctl", 40, "", "replay"],
         [3, 6, "R", 42, 7, "trail", 8, "", "replay"]],
    )
    (trail / "manifest.json").write_text(
        json.dumps({"result_schema": TRAIL_SCHEMA})
    )
    if registry:
        (analysis / "experiments.json").write_text(
            json.dumps(
                {
                    "registry_version": 1,
                    "experiments": [
                        {"experiment_id": "btc.ema500.ratio", "title": "Ratio", "ticker": "BTC",
                         "anchor": "EMA500", "manifest": "BTC/ema500/ratio/manifest.json"},
                        {"experiment_id": "btc.ema500.trail", "title": "Trail", "ticker": "BTC",
                         "anchor": "EMA500", "manifest": "BTC/ema500/trail/manifest.json"},
                    ],
                }
            )
        )
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    settings = Settings(artifacts_root=runs, configs_root=tmp_path / "configs")
    container = _container(runs)
    return TestClient(create_app(settings, container))


def test_registry_is_returned_as_is(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/api/research/experiments").json()
    assert [e["experiment_id"] for e in body["experiments"]] == ["btc.ema500.ratio", "btc.ema500.trail"]
    assert set(body["experiments"][0]) == {"experiment_id", "title", "ticker", "anchor", "manifest"}


def test_missing_registry_is_empty(tmp_path: Path) -> None:
    body = _client(tmp_path, registry=False).get("/api/research/experiments").json()
    assert body["experiments"] == []


def test_manifest_and_unknown_experiment(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/research/experiments/btc.ema500.ratio").json()["test_id"] == "ratio_4d"
    unknown = client.get("/api/research/experiments/nope")
    assert unknown.status_code == 404 and unknown.json()["error"] == "experiment_not_found"
    assert client.get("/api/research/experiments/nope/results").status_code == 404


def test_results_slice_by_semantic_id(tmp_path: Path) -> None:
    body = _client(tmp_path).get(
        "/api/research/experiments/btc.ema500.ratio/results", params={"sl": "3"}
    ).json()
    assert body["rows"] == 1
    cols = dict(zip(body["columns"], body["data"], strict=True))
    assert cols["width"] == [3] and cols["lookback"] == [20] and cols["sl"] == [3]
    assert cols["return_pct"] == [0.25] and cols["run_id"] == ["run_" + "a" * 32]
    assert cols["market_data_hash"] == ["h1"]
    assert body["provenance"] == {"value": "engine"}
    assert "min_current_width_atr" not in body["columns"]


def test_column_selection_and_unknown_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)
    url = "/api/research/experiments/btc.ema500.ratio/results"
    body = client.get(url, params={"columns": "sl,return_pct"}).json()
    assert body["columns"] == ["sl", "return_pct"] and body["rows"] == 2
    assert client.get(url, params={"columns": "nope"}).status_code == 400
    assert client.get(url, params={"min_current_width_atr": "3"}).status_code == 400


def test_multi_grid_dimension_and_arm(tmp_path: Path) -> None:
    client = _client(tmp_path)
    url = "/api/research/experiments/btc.ema500.trail/results"
    body = client.get(url, params={"grid": "R", "trigger": "7", "sl": "5"}).json()
    cols = dict(zip(body["columns"], body["data"], strict=True))
    assert body["rows"] == 1 and cols["trigger.R"] == [7] and cols["trigger.ATR"] == [35]
    assert cols["net"] == [100.5]
    assert cols["run_id"] == ["run_" + "c" * 32] and cols["provenance"] == ["replay"]
    assert "provenance" not in body or body["provenance"] != {"value": "engine"}
    ctl = client.get(url, params={"arm": "ctl"}).json()
    assert ctl["rows"] == 1
    assert client.get(url, params={"trigger": "7"}).status_code == 400  # needs a grid
    assert client.get(url, params={"grid": "XX", "trigger": "7"}).status_code == 400


def test_missing_run_bundle_does_not_invalidate(tmp_path: Path) -> None:
    client = _client(tmp_path)  # no run bundles exist at all
    body = client.get("/api/research/experiments/btc.ema500.ratio/results").json()
    assert body["rows"] == 2


def test_malformed_experiment_affects_only_itself(tmp_path: Path) -> None:
    client = _client(tmp_path)
    (tmp_path / "analysis" / "BTC" / "ema500" / "trail" / "runs.csv").write_text("w,sl\n1,2\n")
    bad = client.get("/api/research/experiments/btc.ema500.trail/results")
    assert bad.status_code == 500 and bad.json()["error"] == "experiment_invalid"
    assert "lacks declared columns" in bad.json()["message"]
    assert client.get("/api/research/experiments/btc.ema500.ratio/results").status_code == 200


def test_no_surface_cells_aggregates_or_findings_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    paths = set(client.get("/openapi.json").json()["paths"])
    experiment_paths = {p for p in paths if p.startswith("/api/research/experiments")}
    assert experiment_paths == {
        "/api/research/experiments",
        "/api/research/experiments/{experiment_id}",
        "/api/research/experiments/{experiment_id}/results",
        # research-experiment-storage-v1: read-only counts and size
        "/api/research/experiments/{experiment_id}/storage",
        # research-run-deletion-v1: the only write routes
        "/api/research/experiments/{experiment_id}/runs/delete-plan",
        "/api/research/experiments/{experiment_id}/runs/delete",
    }
    assert not any("surface" in p or "cells" in p or "aggregates" in p for p in paths)


def test_analysis_root_is_sibling_of_artifacts_root() -> None:
    settings = Settings(artifacts_root=Path("/data/runs"))
    assert settings.analysis_root == Path("/data/analysis")
