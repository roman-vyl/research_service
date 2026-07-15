from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.experiments.models import (
    BatchValidationError,
    ExperimentBatchResult,
    ExperimentCandidateResult,
    ExperimentCandidateSpec,
    ExperimentBatchSpec,
    load_batch_spec,
)
from research.experiments.storage import write_batch_result
from research.experiments.validation import file_sha256, load_and_validate_batch_spec


def _candidate_config(path: Path, *, fast: int = 100) -> None:
    payload = {
        "schema_version": 1,
        "experiment_id": path.stem,
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0006, "slippage": 0.0001},
        "instances": [
            {
                "instance_id": f"baseline_fast{fast}",
                "variant": f"ema_pullback_fast{fast}_anchor200_slow1000",
                "market": {"symbol": "BTCUSDT", "base_timeframe": "1h"},
                "strategy": {
                    "trade_sides": ["long"],
                    "anchor_stack": {
                        "source": "close",
                        "timeframe": "base",
                        "fast": fast,
                        "anchor": 200,
                        "slow": 1000,
                    },
                    "direction": {"component_id": "ema_anchor_stack_trend"},
                    "setup": {
                        "component_id": "untouched_anchor_setup",
                        "lookback": 50,
                        "active_bars": 3,
                    },
                    "trigger": {"component_id": "reclaim_anchor"},
                    "blockers": [{"instance_id": "no_blockers", "component_id": "no_blockers"}],
                    "risk": {"component_id": "no_risk_filter"},
                    "contexts": {},
                    "trade_management": {
                        "exit_policy": {
                            "always_on": {
                                "exits": [
                                    {
                                        "instance_id": "atr_stop_loss",
                                        "component_id": "atr_stop_loss",
                                        "distance": {"timeframe": "base", "period": 14, "multiplier": 1.5},
                                    }
                                ]
                            },
                            "profiles": {
                                "aligned": {"exits": []},
                                "countertrend": {"exits": []},
                                "neutral": {"exits": []},
                            },
                        }
                    },
                },
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _batch_spec(path: Path, candidates: list[dict[str, object]]) -> None:
    payload = {
        "experiment_id": "batch_test_001",
        "family": "ema_pullback",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "candidates": candidates,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_batch_result_serializes_hashes_timing_and_run_id(tmp_path: Path) -> None:
    candidate = ExperimentCandidateResult(
        candidate_id="c1",
        status="ok",
        strategy_config_path="research/experiments/specs/candidates/a.json",
        strategy_config_hash="abc123",
        run_id="2026-05-24T120000Z_ema_pullback_BTCUSDT_1h",
        report_path="research/results/runs/2026-05-24T120000Z_ema_pullback_BTCUSDT_1h.json",
        config_id="baseline",
        report_schema_version=5,
        started_at="2026-05-24T12:00:00Z",
        finished_at="2026-05-24T12:00:10Z",
        duration_sec=10.0,
        total_trades=10,
        pnl=100.0,
    )
    result = ExperimentBatchResult(
        experiment_id="batch_test_001",
        created_at="2026-05-24T12:00:10Z",
        family="ema_pullback",
        symbol="BTCUSDT",
        timeframe="1h",
        candidates_count=1,
        ok_count=1,
        failed_count=0,
        results=[candidate],
        batch_spec_path="research/experiments/specs/example_batch.json",
        batch_spec_hash="deadbeef",
        started_at="2026-05-24T12:00:00Z",
        finished_at="2026-05-24T12:00:10Z",
        duration_sec=10.0,
    )

    output = write_batch_result(result, batches_dir=tmp_path / "batches")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["batch_spec_hash"] == "deadbeef"
    assert payload["duration_sec"] == 10.0
    assert payload["results"][0]["run_id"].endswith("_BTCUSDT_1h")


def test_duplicate_candidate_id_rejects_before_execution(tmp_path: Path) -> None:
    batch_path = tmp_path / "batch.json"
    _batch_spec(
        batch_path,
        [
            {"candidate_id": "dup", "strategy_config_path": "missing_a.json"},
            {"candidate_id": "dup", "strategy_config_path": "missing_b.json"},
        ],
    )

    with pytest.raises(BatchValidationError, match="duplicate candidate_id"):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)


def test_missing_candidate_config_rejects_during_validation(tmp_path: Path) -> None:
    batch_path = tmp_path / "batch.json"
    _batch_spec(
        batch_path,
        [{"candidate_id": "c1", "strategy_config_path": "research/experiments/specs/missing.json"}],
    )

    with pytest.raises(BatchValidationError, match="does not exist"):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)


def test_multi_instance_candidate_config_rejects_before_execution(tmp_path: Path) -> None:
    config_path = tmp_path / "multi.json"
    payload = json.loads(
        Path("research/experiments/specs/candidates/instance_1.json").read_text(encoding="utf-8")
    )
    payload["instances"].append(payload["instances"][0])
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    batch_path = tmp_path / "batch.json"
    _batch_spec(batch_path, [{"candidate_id": "c1", "strategy_config_path": "multi.json"}])

    with pytest.raises(BatchValidationError, match="exactly one instance"):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)


def test_market_mismatch_rejects_before_execution(tmp_path: Path) -> None:
    config_path = tmp_path / "candidate.json"
    _candidate_config(config_path, fast=100)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["instances"][0]["market"] = {"symbol": "ETHUSDT", "base_timeframe": "1h"}
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    batch_path = tmp_path / "batch.json"
    _batch_spec(batch_path, [{"candidate_id": "c1", "strategy_config_path": "candidate.json"}])

    with pytest.raises(BatchValidationError, match="market mismatch"):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)


def test_validation_does_not_call_strategy_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_a = tmp_path / "a.json"
    config_b = tmp_path / "b.json"
    _candidate_config(config_a, fast=100)
    _candidate_config(config_b, fast=120)

    batch_path = tmp_path / "batch.json"
    _batch_spec(
        batch_path,
        [
            {"candidate_id": "c1", "strategy_config_path": "a.json"},
            {"candidate_id": "c2", "strategy_config_path": "b.json"},
        ],
    )

    def _boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("strategy runner must not be called during validation")

    monkeypatch.setattr(
        "research.strategies.ema_pullback.execution.runner.run_strategy_specs_from_config_returning_paths",
        _boom,
    )

    validated = load_and_validate_batch_spec(batch_path, repo_root=tmp_path)
    assert len(validated.candidates) == 2
    assert validated.candidates[0].strategy_config_hash == file_sha256(config_a)


def test_unsafe_experiment_id_rejected() -> None:
    with pytest.raises(BatchValidationError, match="experiment_id must match"):
        load_batch_spec(
            {
                "experiment_id": "../bad",
                "family": "ema_pullback",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "candidates": [
                    {
                        "candidate_id": "c1",
                        "strategy_config_path": "research/experiments/specs/candidates/instance_1.json",
                    }
                ],
            }
        )


def test_unsafe_candidate_id_rejected() -> None:
    with pytest.raises(BatchValidationError, match="candidate_id must match"):
        load_batch_spec(
            {
                "experiment_id": "batch_test",
                "family": "ema_pullback",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "candidates": [
                    {
                        "candidate_id": "bad/id",
                        "strategy_config_path": "research/experiments/specs/candidates/instance_1.json",
                    }
                ],
            }
        )


def test_candidate_config_without_instances_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "no_instances.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment_id": "candidate_no_instances",
                "family": "ema_pullback",
                "execution": {"init_cash": 10000.0},
            }
        ),
        encoding="utf-8",
    )

    batch_path = tmp_path / "batch.json"
    _batch_spec(batch_path, [{"candidate_id": "c1", "strategy_config_path": "no_instances.json"}])

    with pytest.raises(BatchValidationError, match="exactly one instances item"):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)


def test_load_batch_spec_parses_candidates() -> None:
    spec = load_batch_spec(
        {
            "experiment_id": "x",
            "family": "ema_pullback",
            "symbol": "btcusdt",
            "timeframe": "1h",
            "candidates": [
                {
                    "candidate_id": "c1",
                    "strategy_config_path": "research/experiments/specs/candidates/instance_1.json",
                }
            ],
        }
    )
    assert spec.symbol == "BTCUSDT"
    assert spec.candidates[0] == ExperimentCandidateSpec(
        candidate_id="c1",
        strategy_config_path="research/experiments/specs/candidates/instance_1.json",
        metadata=None,
    )
