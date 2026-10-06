from __future__ import annotations

import copy
import csv
import dataclasses
import hashlib
import json
import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_runs_bff import _container

from research_service.adapters.experiments import FilesystemExperiments, FilesystemRunCalculation
from research_service.adapters.experiments import run_calculation as calc_module
from research_service.api.app import create_app
from research_service.application.experiments.contracts import (
    BatchCandidateResult,
    BatchExperimentRequest,
    BatchExperimentResult,
    BatchSideSummary,
)
from research_service.domain.errors import MarketDataHashMismatch
from research_service.domain.experiment_schema import ResultSchema
from research_service.ports.strategy_engine import StrategySpecValidation
from research_service.runtime.settings import Settings

EXP = "btc.ema500.calc"
BASE = f"/api/research/experiments/{EXP}"
LIVE_RUN = "run_" + "a" * 32
DANGLING_RUN = "run_" + "b" * 32  # filled run_id, no run folder

SCHEMA: dict[str, Any] = {
    "contract_version": "research_experiment_result_schema.v1",
    "table": "runs.csv",
    "run_id_column": "run_id",
    "provenance": {"column": "provenance"},
    "row_columns": {"market_data_hash": "market_data_hash"},
    "dimensions": [
        {"id": "width", "column": "width", "unit": "ATR"},
        {"id": "lookback", "column": "lookback", "unit": "bars"},
        {"id": "sl", "column": "sl", "unit": "ATR"},
    ],
    "metrics": [
        {"column": "return_pct", "label": "Return", "format": "fraction"},
        {"column": "trades", "label": "Trades", "format": "integer"},
        {"column": "profit_factor", "label": "PF", "format": "number"},
    ],
    "view": [{"id": "main", "x": "lookback", "y": "width", "controls": ["sl"], "default_metric": "return_pct"}],
}

MATERIALIZE: dict[str, Any] = {
    "contract_version": "research_experiment_materialize.v1",
    "strategy_template": {
        "enabled": True,
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {
            "setup": {"min_width": 1.0, "lookback": 1},
            "trigger": {"lookback": 12},
            "exits": {"sl": 1.0, "tp": 1.0},
        },
    },
    "bindings": [
        {"column": "width", "path": "/raw_spec/setup/min_width", "type": "number"},
        {"column": "lookback", "path": "/raw_spec/setup/lookback", "type": "integer"},
        {"column": "sl", "path": "/raw_spec/exits/sl", "type": "number"},
        {"column": "tp", "path": "/raw_spec/exits/tp", "type": "number"},
    ],
    "result_bindings": {"return_pct": "return_pct", "trades": "realised_trade_count", "profit_factor": "profit_factor"},
    "research_policy": {
        "range_policy": "explicit_range",
        "range": {"from_ms": 0, "to_ms": 900000},
        "accounting": {"initial_equity": "10000", "entry_fee_rate": "0.0004", "exit_fee_rate": "0.0004"},
        "managed_policy_enabled": True,
    },
}

HEADER = ["width", "lookback", "sl", "tp", "return_pct", "trades", "profit_factor", "run_id", "provenance", "market_data_hash"]
ROWS = [
    [3, 20, 3.0, 9.0, "0.25", 100, "1.5", "", "replay", "h1"],             # 0: agrees within tolerance
    [3, 30, 3.0, 9.0, "0.1", 50, "1.2", "", "replay", "h1"],               # 1: trade count differs
    [4, 20, 3.0, 9.0, "0.3", 70, "1.4", LIVE_RUN, "engine", "h1"],         # 2: live run
    [5, 20, 3.0, 9.0, "-0.05", 40, "0.9", "", "engine", "h1"],             # 3: run deleted
    [6, 20, 3.0, 9.0, "0.0", 1, "1.0", "", "replay", "h1"],                # 4: duplicate
    [6, 20, 3.0, 9.0, "0.0", 1, "1.0", "", "replay", "h1"],                # 5: duplicate
    [7, 20, 3.0, "", "0.0", 1, "1.0", "", "replay", "h1"],                 # 6: empty bound cell
    [8, 20, 3.0, 9.0, "0.0", 1, "1.0", "", "replay", "h1"],                # 7: Engine rejects
    [10, 20, 3.0, 9.0, "0.0", 1, "1.0", DANGLING_RUN, "engine", "h1"],     # 8: run_id without folder
]

# What the fake Engine computes, per (min_width, lookback).
TRUTH = {
    (3.0, 20): (Decimal("0.2500001"), 100, Decimal("1.5000009")),
    (3.0, 30): (Decimal("0.1"), 51, Decimal("1.2")),
    (5.0, 20): (Decimal("-0.05"), 40, Decimal("0.9")),
}


class FakeEngine:
    def __init__(self) -> None:
        self.calls = 0

    def validate_strategy(self, strategy_id: str, raw_spec: dict[str, Any]) -> StrategySpecValidation:
        self.calls += 1
        if raw_spec["setup"]["min_width"] == 8.0:
            return StrategySpecValidation(config_hash=None, error="min_width out of range")
        digest = hashlib.sha256(json.dumps(raw_spec, sort_keys=True).encode()).hexdigest()
        return StrategySpecValidation(config_hash=digest)


class FakeRunner:
    def __init__(self, runs: Path) -> None:
        self.runs = runs
        self.calls: list[tuple[BatchExperimentRequest, str | None]] = []
        self.on_call: Callable[[int], None] | None = None
        self.fail: Exception | None = None

    def execute(
        self, request: BatchExperimentRequest, *, expected_market_data_hash: str | None = None
    ) -> BatchExperimentResult:
        self.calls.append((request, expected_market_data_hash))
        if self.on_call is not None:
            self.on_call(len(self.calls))
        if self.fail is not None:
            raise self.fail
        results = []
        for c in request.candidates:
            setup = c.strategy.raw_spec["setup"]
            ret, trades, pf = TRUTH[(setup["min_width"], setup["lookback"])]
            run_id = "run_" + uuid.uuid4().hex
            (self.runs / run_id).mkdir()
            side = BatchSideSummary(trades=trades, net_pnl=Decimal("0"), return_pct=Decimal("0"))
            results.append(
                BatchCandidateResult(
                    candidate_id=c.candidate_id,
                    run_id=run_id,
                    instance_id="ema_pullback:x",
                    status="completed",
                    realised_trade_count=trades,
                    return_pct=ret,
                    profit_factor=pf,
                    max_drawdown=Decimal("-0.1"),
                    long=side,
                    short=side,
                    market_data_hash=expected_market_data_hash,
                )
            )
        return BatchExperimentResult(
            experiment_id=request.experiment_id,
            status="completed",
            candidate_count=len(results),
            completed_count=len(results),
            failed_count=0,
            candidates=tuple(results),
        )


class FakePersister:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, request: BatchExperimentRequest, result: BatchExperimentResult) -> Any:
        self.calls.append(request.experiment_id)


@dataclasses.dataclass
class Env:
    client: TestClient
    service: FilesystemRunCalculation
    runner: FakeRunner
    engine: FakeEngine
    persister: FakePersister
    folder: Path
    pending: list[Callable[[], None]]

    @property
    def table(self) -> Path:
        return self.folder / "runs.csv"

    def run_pending(self) -> None:
        while self.pending:
            self.pending.pop(0)()


def _setup(
    tmp_path: Path,
    *,
    deferred: bool = False,
    schema: dict[str, Any] | None = None,
    materialize: dict[str, Any] | None = MATERIALIZE,
) -> Env:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / LIVE_RUN).mkdir()
    folder = tmp_path / "analysis" / "BTC" / "calc"
    folder.mkdir(parents=True)
    with (folder / "runs.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(ROWS)
    manifest: dict[str, Any] = {"experiment_id": EXP, "result_schema": schema or SCHEMA}
    if materialize is not None:
        manifest["materialize"] = materialize
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "analysis" / "experiments.json").write_text(
        json.dumps(
            {
                "registry_version": 1,
                "experiments": [
                    {"experiment_id": EXP, "title": "C", "ticker": "BTC", "anchor": "EMA500",
                     "manifest": "BTC/calc/manifest.json"},
                ],
            }
        )
    )
    settings = Settings(artifacts_root=runs, configs_root=tmp_path / "configs")
    app = create_app(settings, _container(runs))
    engine, runner, persister = FakeEngine(), FakeRunner(runs), FakePersister()
    pending: list[Callable[[], None]] = []

    def spawn(target: Callable[[], None]) -> None:
        if deferred:
            pending.append(target)
        else:
            target()

    service = FilesystemRunCalculation(
        FilesystemExperiments(settings.analysis_root), runs, engine, runner, persister, spawn
    )
    app.state.services = dataclasses.replace(app.state.services, run_calculation=service)
    return Env(TestClient(app), service, runner, engine, persister, folder, pending)


def _coords(width: float, lookback: int = 20, sl: float = 3.0) -> dict[str, Any]:
    return {"coords": {"width": width, "lookback": lookback, "sl": sl}}


def _cells(path: Path) -> list[list[str]]:
    with path.open(newline="") as fh:
        return list(csv.reader(fh))


def _plan(env: Env, rows: list[dict[str, Any]]) -> dict[str, Any]:
    resp = env.client.post(f"{BASE}/runs/calculate-plan", json={"rows": rows})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def _calculate(env: Env, rows: list[dict[str, Any]]) -> str:
    plan = _plan(env, rows)
    resp = env.client.post(f"{BASE}/runs/calculate", json={"rows": rows, "plan_token": plan["plan_token"]})
    assert resp.status_code == 202, resp.text
    return resp.json()["job_id"]  # type: ignore[no-any-return]


def _status(env: Env, job_id: str) -> dict[str, Any]:
    resp = env.client.get(f"{BASE}/calculations/{job_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def test_plan_reasons_and_changes_nothing(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    before = env.table.read_bytes()
    rows = [
        _coords(3), _coords(3, 30), _coords(4), _coords(5), _coords(6), _coords(7), _coords(8), _coords(99),
        _coords(10),
    ]
    plan = _plan(env, rows)
    status = [(r["status"], r.get("reason")) for r in plan["rows"]]
    assert status == [
        ("calculable", None),
        ("calculable", None),
        ("skipped", "has_run"),
        ("calculable", None),
        ("skipped", "ambiguous_row"),
        ("skipped", "binding_value_invalid"),
        ("skipped", "invalid_spec"),
        ("skipped", "row_not_found"),
        ("skipped", "has_run"),
    ]
    assert plan["rows"][6]["message"] == "min_width out of range"
    assert plan["calculable_count"] == 3 and plan["plan_token"].startswith("sha256:")
    assert env.table.read_bytes() == before
    assert env.runner.calls == [] and env.pending == []
    assert not list(env.folder.glob("*.pre_calculate_*")) and not (env.folder / "runs_calculated.jsonl").exists()


def test_materialize_copies_bound_values_into_the_template(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    _calculate(env, [_coords(3, 30)])
    request, expected = env.runner.calls[0]
    assert expected == "h1"
    candidate = request.candidates[0]
    assert candidate.strategy.raw_spec == {
        "setup": {"min_width": 3.0, "lookback": 30},
        "trigger": {"lookback": 12},
        "exits": {"sl": 3.0, "tp": 9.0},
    }
    assert candidate.accounting.entry_fee_rate == Decimal("0.0004")
    assert request.range is not None and request.range.to_ms == 900000
    assert MATERIALIZE["strategy_template"]["raw_spec"]["setup"]["min_width"] == 1.0


def test_calculate_publishes_only_rows_that_pass_metric_parity(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    before = _cells(env.table)
    job_id = _calculate(env, [_coords(3), _coords(3, 30), _coords(5)])
    status = _status(env, job_id)
    assert status["state"] == "completed"
    outcomes = {tuple(r["coords"].values()): r for r in status["rows"]}
    assert outcomes[(3, 20, 3.0)]["outcome"] == "published"
    failed = outcomes[(3, 30, 3.0)]
    assert failed["outcome"] == "parity_failed"
    assert failed["parity"] == [{"column": "trades", "expected": "50", "actual": "51"}]
    assert outcomes[(5, 20, 3.0)]["outcome"] == "published"
    assert len(env.runner.calls) == 1 and len(env.persister.calls) == 1

    after = _cells(env.table)
    assert after[0] == before[0]
    row0 = dict(zip(after[0], after[1]))
    assert row0["return_pct"] == "0.2500001" and row0["profit_factor"] == "1.5000009"
    assert row0["provenance"] == "engine" and row0["run_id"] == outcomes[(3, 20, 3.0)]["run_id"]
    assert row0["width"] == "3" and row0["tp"] == "9.0" and row0["market_data_hash"] == "h1"
    assert after[2] == before[2]  # parity failed: untouched
    row3 = dict(zip(after[0], after[4]))
    assert row3["run_id"] == outcomes[(5, 20, 3.0)]["run_id"] and row3["provenance"] == "engine"
    for i in (3, 5, 6, 7, 8, 9):
        assert after[i] == before[i]
    assert (tmp_path / "runs" / failed["run_id"]).is_dir()  # diagnostic run kept, not linked
    assert failed["run_id"] not in env.table.read_text()
    assert b"\r\n" in env.table.read_bytes()

    backups = list(env.folder.glob("runs.pre_calculate_*.csv"))
    assert len(backups) == 1 and _cells(backups[0]) == before
    journal = [json.loads(line) for line in (env.folder / "runs_calculated.jsonl").read_text().splitlines()]
    assert sorted(j["outcome"] for j in journal) == ["parity_failed", "published", "published"]

    results = env.client.get(f"{BASE}/results", params={"width": "3", "lookback": "20"}).json()
    data = dict(zip(results["columns"], results["data"]))
    assert data["provenance"] == ["engine"] and data["run_id"] == [row0["run_id"]]

    # A calculated row now has a run: planning it again skips it.
    assert _plan(env, [_coords(3)])["rows"][0]["reason"] == "has_run"


def test_integer_metric_is_exact_and_empty_values(tmp_path: Path) -> None:
    schema = ResultSchema.model_validate(SCHEMA)
    parity = calc_module._parity
    assert parity(schema, {"trades": "100"}, {"trades": 100}) == []
    assert parity(schema, {"trades": "100"}, {"trades": 101}) != []
    assert parity(schema, {"profit_factor": "1"}, {"profit_factor": Decimal("1.000001")}) == []
    assert parity(schema, {"profit_factor": "1"}, {"profit_factor": Decimal("1.00001")}) != []
    assert parity(schema, {"profit_factor": "0"}, {"profit_factor": Decimal("1e-10")}) == []
    assert parity(schema, {"profit_factor": "0"}, {"profit_factor": Decimal("1e-8")}) != []
    assert parity(schema, {"profit_factor": ""}, {"profit_factor": None}) == []
    assert parity(schema, {"profit_factor": ""}, {"profit_factor": Decimal("1")}) != []
    assert parity(schema, {"profit_factor": "1"}, {"profit_factor": None}) != []


def test_stale_plan_token(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    rows = [_coords(3)]
    plan = _plan(env, rows)
    with env.table.open("a", newline="") as fh:
        csv.writer(fh, lineterminator="\r\n").writerow([9, 20, 3.0, 9.0, "0", 1, "1", "", "replay", "h1"])
    resp = env.client.post(f"{BASE}/runs/calculate", json={"rows": rows, "plan_token": plan["plan_token"]})
    assert resp.status_code == 409 and resp.json()["error"] == "plan_stale"
    assert env.runner.calls == []


def test_row_changed_during_job_is_not_published(tmp_path: Path) -> None:
    env = _setup(tmp_path, deferred=True)
    job_id = _calculate(env, [_coords(3), _coords(5)])
    cells = _cells(env.table)
    cells[1][6] = "1.7"
    with env.table.open("w", newline="") as fh:
        csv.writer(fh, lineterminator="\r\n").writerows(cells)
    env.run_pending()
    status = _status(env, job_id)
    outcomes = {r["coords"]["width"]: r["outcome"] for r in status["rows"]}
    assert outcomes == {3: "row_stale", 5: "published"}
    assert _cells(env.table)[1] == cells[1]


def test_cancel_between_batch_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(calc_module, "BATCH_SIZE", 1)
    env = _setup(tmp_path, deferred=True)
    job_id = _calculate(env, [_coords(3), _coords(5), _coords(3, 30)])

    def cancel_after_first(n: int) -> None:
        if n == 1:
            assert env.client.post(f"{BASE}/calculations/{job_id}/cancel").status_code == 200

    env.runner.on_call = cancel_after_first
    env.run_pending()
    status = _status(env, job_id)
    assert status["state"] == "cancelled"
    assert [r["outcome"] for r in status["rows"]] == ["published", "cancelled", "cancelled"]
    assert len(env.runner.calls) == 1


def test_batch_calls_hold_at_most_1000_variants(tmp_path: Path) -> None:
    assert calc_module.BATCH_SIZE == 1000 and calc_module.MAX_ROWS == 2000


def test_market_data_mismatch_fails_the_rows(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    before = env.table.read_bytes()
    env.runner.fail = MarketDataHashMismatch("h1", "h2")
    job_id = _calculate(env, [_coords(3)])
    status = _status(env, job_id)
    assert status["state"] == "completed"
    assert status["rows"][0]["outcome"] == "engine_failed"
    assert "h2" in status["rows"][0]["message"]
    assert env.table.read_bytes() == before


def test_one_job_at_a_time(tmp_path: Path) -> None:
    env = _setup(tmp_path, deferred=True)
    _calculate(env, [_coords(3)])
    resp = env.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [_coords(5)]})
    assert resp.status_code == 409 and resp.json()["error"] == "job_running"
    env.run_pending()
    assert _plan(env, [_coords(5)])["calculable_count"] == 1


@pytest.mark.parametrize(
    ("schema_patch", "materialize", "code"),
    [
        ({}, None, "materialize_missing"),
        ({"metrics": SCHEMA["metrics"] + [{"column": "sl", "label": "x", "format": "number"}]}, MATERIALIZE,
         "unbound_metric"),
        ({"provenance": {"value": "replay"}}, MATERIALIZE, "provenance_not_per_row"),
    ],
)
def test_experiment_level_rejections(
    tmp_path: Path, schema_patch: dict[str, Any], materialize: dict[str, Any] | None, code: str
) -> None:
    env = _setup(tmp_path, schema={**SCHEMA, **schema_patch}, materialize=materialize)
    resp = env.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [_coords(3)]})
    assert resp.status_code == 409 and resp.json()["error"] == code


def test_engine_provenance_constant_is_calculable(tmp_path: Path) -> None:
    schema = {**SCHEMA, "provenance": {"value": "engine"}}
    env = _setup(tmp_path, schema=schema)
    job_id = _calculate(env, [_coords(5)])
    assert _status(env, job_id)["rows"][0]["outcome"] == "published"
    row = dict(zip(*_cells(env.table)[0:5:4]))
    assert row["provenance"] == "engine" and row["run_id"].startswith("run_")


def test_invalid_block_and_request_errors(tmp_path: Path) -> None:
    bad = copy.deepcopy(MATERIALIZE)
    bad["bindings"][0]["path"] = "/raw_spec/setup/missing"
    env = _setup(tmp_path, materialize=bad)
    resp = env.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [_coords(3)]})
    assert resp.status_code == 500 and resp.json()["error"] == "experiment_invalid"

    (tmp_path / "b").mkdir()
    env2 = _setup(tmp_path / "b")
    resp = env2.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [_coords(3)] * 2001})
    assert resp.status_code == 422 and resp.json()["error"] == "too_many_rows"
    resp = env2.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [{"coords": {"width": 3}}]})
    assert resp.status_code == 400
    resp = env2.client.get(f"{BASE}/calculations/calc_nope")
    assert resp.status_code == 404


def test_grid_and_arm_coordinates(tmp_path: Path) -> None:
    schema = ResultSchema.model_validate(
        {
            **SCHEMA,
            "dimensions": [
                {"id": "width", "column": "w", "unit": "ATR"},
                {"id": "trigger", "grid_column": "grid",
                 "grids": {"ATR": {"column": "t_atr", "unit": "ATR"}, "R": {"column": "t_r", "unit": "R"}}},
            ],
            "arms": {"column": "arm", "roles": {"trail": "treatment", "ctl": "comparison"},
                     "baseline": "ctl", "match_on": ["width"]},
        }
    )
    keys = calc_module._Keys(schema)
    header = ["w", "grid", "t_atr", "t_r", "arm"]
    row = ["3", "R", "35", "7", "trail"]
    assert keys.row_key(header, row) == keys.request_key({"width": 3, "trigger": 7, "grid": "R", "arm": "trail"}, 0)
    assert keys.row_key(header, row) != keys.request_key({"width": 3, "trigger": 35, "grid": "R", "arm": "trail"}, 0)
