from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.experiments.batch_runner import BatchRunner
from research.experiments.models import BatchValidationError
from research.experiments.models import ExperimentCandidateResult
from research.experiments.summary import apply_summary_to_result, extract_candidate_summary
from research.experiments.validation import load_and_validate_batch_spec


def _profile_side_breakdown_fixture() -> dict[str, object]:
    leaf = {
        "trades": 2,
        "pnl": 4.0,
        "gross_pnl": 4.5,
        "fees_paid": 0.5,
        "profit_factor": 2.0,
        "win_rate": 0.5,
        "avg_return_pct": 0.01,
        "avg_hold_bars": 3.0,
        "exit_reason_mix": {"signal:ema": 2},
    }
    empty_leaf = {
        "trades": 0,
        "pnl": 0.0,
        "gross_pnl": 0.0,
        "fees_paid": 0.0,
        "profit_factor": None,
        "win_rate": None,
        "avg_return_pct": None,
        "avg_hold_bars": None,
        "exit_reason_mix": {},
    }
    profile_triplet = {
        "aligned": dict(leaf),
        "countertrend": dict(empty_leaf),
        "neutral": dict(empty_leaf),
        "total": dict(leaf),
    }
    return {
        "long": dict(profile_triplet),
        "short": {
            "aligned": dict(empty_leaf),
            "countertrend": dict(empty_leaf),
            "neutral": dict(empty_leaf),
            "total": dict(empty_leaf),
        },
        "total": dict(profile_triplet),
    }


def _v5_report(*, with_quality: bool = True, with_profile_side: bool = True) -> dict[str, object]:
    metrics: dict[str, object] = {
        "total": {
            "trades": 1,
            "pnl": 100.0,
            "return_pct": 0.01,
            "profit_factor": 1.2,
            "win_rate": 1.0,
            "sharpe": 0.5,
            "max_drawdown": -0.02,
        }
    }
    if with_quality:
        metrics["fee_diagnostics"] = {"gross_pnl": 110.0, "total_fees_paid": 10.0}
        metrics["quality_flag_breakdown"] = {
            "high_mfe_low_capture": {"trades": 1},
            "signal_exit_winner": {"trades": 2},
        }
    if with_profile_side:
        metrics["profile_side_breakdown"] = _profile_side_breakdown_fixture()

    return {
        "run_id": "2026-05-24T120000Z_ema_pullback_BTCUSDT_5m_fixture",
        "report_schema_version": 5 if with_quality else 4,
        "variants": [
            {
                "config_id": "fixture_v5",
                "metrics": metrics,
            }
        ],
    }


def _write_candidate(path: Path, *, fast: int) -> None:
    payload = json.loads(
        Path("research/experiments/specs/candidates/instance_1.json").read_text(encoding="utf-8")
    )
    payload["experiment_id"] = path.stem
    payload["instances"][0]["instance_id"] = f"baseline_fast{fast}"
    payload["instances"][0]["variant"] = f"ema_pullback_fast{fast}_anchor200_slow1000"
    payload["instances"][0]["strategy"]["anchor_stack"]["fast"] = fast
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_batch(tmp_path: Path) -> Path:
    config_a = tmp_path / "candidate_a.json"
    config_b = tmp_path / "candidate_b.json"
    _write_candidate(config_a, fast=100)
    _write_candidate(config_b, fast=120)

    batch_path = tmp_path / "batch.json"
    batch_path.write_text(
        json.dumps(
            {
                "experiment_id": "batch_runner_test",
                "family": "ema_pullback",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "candidates": [
                    {"candidate_id": "c1", "strategy_config_path": "candidate_a.json"},
                    {"candidate_id": "c2", "strategy_config_path": "candidate_b.json"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return batch_path


def test_extract_candidate_summary_v5_quality_counts() -> None:
    summary = extract_candidate_summary(_v5_report(with_quality=True))

    assert summary["run_id"] == "2026-05-24T120000Z_ema_pullback_BTCUSDT_5m_fixture"
    assert summary["config_id"] == "fixture_v5"
    assert summary["report_schema_version"] == 5
    assert summary["total_trades"] == 1
    assert summary["gross_pnl"] == 110.0
    assert summary["fees_paid"] == 10.0
    assert summary["high_mfe_low_capture_count"] == 1
    assert summary["signal_exit_winners"] == 2
    assert summary["high_mfe_high_capture_count"] is None


def test_extract_candidate_summary_v4_null_quality_counts() -> None:
    summary = extract_candidate_summary(_v5_report(with_quality=False, with_profile_side=False))

    assert summary["report_schema_version"] == 4
    assert summary["high_mfe_low_capture_count"] is None
    assert summary["signal_exit_winners"] is None
    assert summary["total_trades"] == 1
    assert summary["long_trades"] is None
    assert summary["aligned_gross_pnl"] is None


def test_extract_candidate_summary_v5_profile_side_fields() -> None:
    summary = extract_candidate_summary(_v5_report(with_quality=True, with_profile_side=True))

    assert summary["long_trades"] == 2
    assert summary["long_pnl"] == 4.0
    assert summary["long_gross_pnl"] == 4.5
    assert summary["long_fees_paid"] == 0.5
    assert summary["long_profit_factor"] == 2.0
    assert summary["long_win_rate"] == 0.5
    assert summary["short_trades"] == 0
    assert summary["short_pnl"] == 0.0
    assert summary["aligned_trades"] == 2
    assert summary["aligned_gross_pnl"] == 4.5
    assert summary["aligned_fees_paid"] == 0.5
    assert summary["long_aligned_trades"] == 2
    assert summary["long_aligned_pnl"] == 4.0
    assert summary["long_aligned_gross_pnl"] == 4.5
    assert summary["short_countertrend_fees_paid"] == 0.0
    assert summary["countertrend_profit_factor"] is None


def test_extract_candidate_summary_v5_without_profile_side_breakdown() -> None:
    summary = extract_candidate_summary(_v5_report(with_quality=True, with_profile_side=False))

    assert summary["total_trades"] == 1
    assert summary["pnl"] == 100.0
    assert summary["long_trades"] is None
    assert summary["long_aligned_gross_pnl"] is None
    assert summary["aligned_fees_paid"] is None


def test_extract_candidate_summary_ignores_trade_management_optional_fields() -> None:
    report = _v5_report(with_quality=True, with_profile_side=True)
    variant = report["variants"][0]
    assert isinstance(variant, dict)
    metrics = variant["metrics"]
    assert isinstance(metrics, dict)
    metrics["trade_management_summary"] = {
        "by_phase_reached": {"runner": {"trade_count": 1}},
    }
    variant["trade_management_events"] = [{"event_type": "phase_changed"}]

    summary = extract_candidate_summary(report)

    assert summary["total_trades"] == 1
    assert summary["pnl"] == 100.0
    assert summary["long_trades"] == 2
    assert "trade_management_summary" not in summary


def test_apply_summary_profile_side_round_trip() -> None:
    summary = extract_candidate_summary(_v5_report(with_profile_side=True))
    result = ExperimentCandidateResult(
        candidate_id="c1",
        status="ok",
        strategy_config_path="x.json",
        strategy_config_hash="abc",
    )
    apply_summary_to_result(result, summary)
    payload = result.to_payload()
    assert payload["long_aligned_gross_pnl"] == 4.5
    assert payload["aligned_fees_paid"] == 0.5


def test_batch_runner_collects_full_result_shape(tmp_path: Path) -> None:
    batch_path = _write_batch(tmp_path)
    validated = load_and_validate_batch_spec(batch_path, repo_root=tmp_path)

    reports: dict[str, dict[str, object]] = {
        "candidate_a.json": _v5_report(with_quality=True),
        "candidate_b.json": _v5_report(with_quality=True),
    }

    def fake_run(config_path: str | Path, _candidate_id: str) -> tuple[str, Path, Path]:
        path = Path(config_path)
        run_id = f"run_{path.stem}"
        run_path = tmp_path / "runs" / f"{run_id}.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(reports[path.name])
        payload["run_id"] = run_id
        run_path.write_text(json.dumps(payload), encoding="utf-8")
        return run_id, tmp_path / "latest.json", run_path

    runner = BatchRunner(run_candidate=fake_run, repo_root=tmp_path)
    result = runner.run(validated)

    assert result.candidates_count == 2
    assert result.ok_count == 2
    assert result.failed_count == 0
    assert result.batch_spec_hash
    assert result.duration_sec >= 0

    first = result.results[0]
    assert first.status == "ok"
    assert first.run_id == "run_candidate_a"
    assert first.report_path.endswith("runs/run_candidate_a.json")
    assert first.strategy_config_hash
    assert first.total_trades == 1


def test_runtime_failure_isolation(tmp_path: Path) -> None:
    batch_path = _write_batch(tmp_path)
    validated = load_and_validate_batch_spec(batch_path, repo_root=tmp_path)

    def fake_run(config_path: str | Path, _candidate_id: str) -> tuple[str, Path, Path]:
        path = Path(config_path)
        if path.name == "candidate_a.json":
            raise RuntimeError("boom")
        run_id = "run_candidate_b"
        run_path = tmp_path / "runs" / f"{run_id}.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _v5_report(with_quality=True)
        payload["run_id"] = run_id
        run_path.write_text(json.dumps(payload), encoding="utf-8")
        return run_id, tmp_path / "latest.json", run_path

    result = BatchRunner(run_candidate=fake_run, repo_root=tmp_path).run(validated)

    assert result.ok_count == 1
    assert result.failed_count == 1
    assert result.results[0].status == "failed"
    assert result.results[0].error == "boom"
    assert result.results[1].status == "ok"


def test_batch_runner_passes_candidate_id_as_run_id_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    batch_path = _write_batch(tmp_path)
    validated = load_and_validate_batch_spec(batch_path, repo_root=tmp_path)
    seen_suffixes: list[str | None] = []

    def fake_returning_paths(
        config_path: str | Path,
        *,
        db_path=None,
        run_id_suffix: str | None = None,
    ) -> tuple[str, Path, Path]:
        seen_suffixes.append(run_id_suffix)
        run_id = f"2026-05-24T120000Z_ema_pullback_BTCUSDT_1h__{run_id_suffix}"
        run_path = tmp_path / "runs" / f"{run_id}.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(json.dumps(_v5_report(with_quality=True) | {"run_id": run_id}), encoding="utf-8")
        return run_id, tmp_path / "latest.json", run_path

    monkeypatch.setattr(
        "research.strategies.ema_pullback.execution.runner.run_strategy_specs_from_config_returning_paths",
        fake_returning_paths,
    )

    result = BatchRunner(repo_root=tmp_path).run(validated)

    assert seen_suffixes == ["c1", "c2"]
    assert result.results[0].run_id.endswith("__c1")
    assert result.results[1].run_id.endswith("__c2")
    assert result.results[0].run_id != result.results[1].run_id


def test_invalid_batch_validation_fails_before_runner(tmp_path: Path) -> None:
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(
        json.dumps(
            {
                "experiment_id": "bad",
                "family": "ema_pullback",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "candidates": [
                    {"candidate_id": "c1", "strategy_config_path": "missing.json"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BatchValidationError):
        load_and_validate_batch_spec(batch_path, repo_root=tmp_path)
