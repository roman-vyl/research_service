"""RunReport contract — reject prototype fields, accept current writer output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.workbench_api

from research_api.contracts.runs import RunReport, TradeRecord
from research_api.services.results_reader import parse_run_report
from research.strategies.ema_pullback.execution.results import (
    baseline_vs_managed_summary_placeholder,
)


def _minimal_trade(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "trade_id": 1,
        "direction": "long",
        "status": "closed",
        "entry_time_ms": 1_000_000,
        "exit_time_ms": 1_100_000,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "exit_reason": "signal:exit",
        "size": 1.0,
        "pnl": 1.0,
        "return_pct": 0.01,
    }
    base.update(overrides)
    return base


def _minimal_report_payload(**variant_overrides: object) -> dict[str, object]:
    variant: dict[str, object] = {
        "variant": "exp_a",
        "config_id": "cfg_a",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "strategy_spec": {"variant": "exp_a"},
        "metrics": {
            "long": {
                "trades": 1,
                "pnl": 1.0,
                "return_pct": 0.01,
                "profit_factor": None,
                "win_rate": 1.0,
            },
            "short": {
                "trades": 0,
                "pnl": 0.0,
                "return_pct": 0.0,
                "profit_factor": None,
                "win_rate": None,
            },
            "total": {
                "trades": 1,
                "pnl": 1.0,
                "return_pct": 0.01,
                "profit_factor": None,
                "win_rate": 1.0,
                "sharpe": 0.1,
                "max_drawdown": -0.01,
            },
            "open_trades": {"long": 0, "short": 0, "total": 0},
        },
        "component_counters": [],
        "trade_records": [_minimal_trade()],
    }
    variant.update(variant_overrides)
    return {
        "run_id": "2026-01-01T000000Z_ema_pullback_BTCUSDT_5m_test",
        "created_at": "2026-01-01T00:00:00Z",
        "report_schema_version": 5,
        "family": "ema_pullback",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "candles": 10,
        "data_range": {"from_open_time_ms": 1_000_000, "to_open_time_ms": 2_000_000},
        "variants_count": 1,
        "variants": [variant],
    }


def test_parse_run_report_accepts_v5_minimal_payload() -> None:
    report = parse_run_report(_minimal_report_payload())
    assert report.report_schema_version == 5
    assert report.variants[0].trade_records[0].trade_id == 1


def test_trade_record_accepts_managed_path_bar_indices_and_break_even() -> None:
    trade = TradeRecord.model_validate(
        _minimal_trade(
            entry_idx=835,
            exit_idx=846,
            break_even={
                "enabled": True,
                "instance_id": "be_ao",
                "trigger_r": 1.0,
                "trigger_price": 101.5,
                "triggered": True,
                "trigger_time_ms": 1_050_000,
                "stop_moved_to": 100.0,
                "initial_stop_price": 98.0,
                "initial_risk": 2.0,
                "active_stop_management_source": "always_on",
            },
        )
    )
    assert trade.entry_idx == 835
    assert trade.break_even is not None
    assert trade.break_even.triggered is True
    report = parse_run_report(
        _minimal_report_payload(
            trade_records=[
                _minimal_trade(
                    entry_idx=10,
                    exit_idx=20,
                    break_even={
                        "enabled": True,
                        "instance_id": "be_al",
                        "trigger_r": 2.0,
                        "triggered": False,
                        "initial_stop_price": 50.0,
                        "initial_risk": 5.0,
                        "active_stop_management_source": "profile",
                    },
                )
            ],
        )
    )
    assert report.variants[0].trade_records[0].break_even is not None


def test_parse_run_report_rejects_prototype_trade_context_ref() -> None:
    payload = _minimal_report_payload(
        trade_records=[_minimal_trade(context_ref="htf")],
    )
    with pytest.raises(ValidationError, match="context_ref"):
        parse_run_report(payload)


def test_trade_record_model_forbids_context_ref() -> None:
    with pytest.raises(ValidationError, match="context_ref"):
        TradeRecord.model_validate(_minimal_trade(context_ref="htf"))


def test_parse_run_report_accepts_entry_setup_diagnostics_namespaced() -> None:
    payload = _minimal_report_payload(
        trade_records=[
            _minimal_trade(
                entry_setup_diagnostics={
                    "untouched_anchor": {
                        "side": "long",
                    },
                    "bounce_counter": {
                        "trend_episode_id": 7,
                        "effective_bounce_number": 2,
                        "completed_bounce_count": 1,
                        "side": "long",
                    },
                },
            ),
        ],
    )
    report = parse_run_report(payload)
    diag = report.variants[0].trade_records[0].entry_setup_diagnostics
    assert set(diag.keys()) == {"untouched_anchor", "bounce_counter"}
    assert diag["bounce_counter"]["trend_episode_id"] == 7
    assert diag["bounce_counter"]["effective_bounce_number"] == 2


def test_parse_run_report_defaults_missing_entry_setup_diagnostics() -> None:
    report = parse_run_report(_minimal_report_payload())
    assert report.variants[0].trade_records[0].entry_setup_diagnostics == {}


def test_trade_record_rejects_flat_bounce_counter_entry_fields() -> None:
    with pytest.raises(ValidationError, match="entry_trend_episode_id"):
        TradeRecord.model_validate(_minimal_trade(entry_trend_episode_id=7))


def _trade_management_block(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "phase_at_exit": "runner",
        "max_phase_reached": "runner",
        "active_stop_source_at_exit": None,
        "active_stop_price_at_exit": None,
        "exit_layer": "stop_loss",
        "exit_owner": "exit_policy",
        "exit_rule_id": "atr_sl",
        "exit_component_id": "atr_stop_loss",
        "best_price_before_exit": 106.0,
        "giveback_from_best_price_pct": 0.01,
        "capture_ratio": 0.5,
        "mfe_pct": 0.06,
        "bars_to_proven": 1,
        "mfe_at_proven_pct": 0.02,
        "bars_to_protected": 2,
        "mfe_at_protected_pct": 0.04,
        "bars_to_runner": 4,
        "mfe_at_runner_pct": 0.06,
    }
    base.update(overrides)
    return base


def _trade_management_event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "trade_id": "1",
        "time_ms": 1_050_000,
        "bar_index": 5,
        "side": "long",
        "event_type": "phase_changed",
        "from_phase": "initial_risk",
        "to_phase": "proven",
        "rule_id": "to_proven_at_1atr",
        "component_id": None,
        "price": 102.0,
        "stop_price": None,
        "mfe_pct": 0.02,
        "mae_pct": 0.01,
        "bars_in_trade": 2,
        "metadata": {"condition_type": "mfe_atr"},
    }
    base.update(overrides)
    return base


def _trade_management_summary_fixture() -> dict[str, object]:
    return {
        "by_phase_reached": {
            "initial_risk": {"trade_count": 1, "share_of_all_trades": 1.0},
            "runner": {"trade_count": 1, "share_of_all_trades": 1.0},
        },
        "phase_transition_counts": {"proven": 1, "runner": 1},
        "exit_layer_breakdown": {"stop_loss": 1},
        "active_stop_source_breakdown": {},
        "runner_capture_summary": {"trade_count": 1, "avg_capture_ratio": 0.5},
        "protected_trade_summary": {
            "trade_count": 1,
            "protected_not_runner_count": 0,
        },
    }


def test_parse_run_report_accepts_old_report_without_trade_management_fields() -> None:
    report = parse_run_report(_minimal_report_payload())
    variant = report.variants[0]
    trade = variant.trade_records[0]

    assert trade.trade_management is None
    assert variant.trade_management_events is None
    assert variant.metrics.trade_management_summary is None


def test_parse_run_report_preserves_diagnostic_only_trade_management_fields() -> None:
    payload = _minimal_report_payload(
        trade_management_events=[
            _trade_management_event(),
            _trade_management_event(
                event_type="exit_executed",
                from_phase="runner",
                to_phase=None,
                bar_index=8,
            ),
        ],
        metrics={
            **_minimal_report_payload()["variants"][0]["metrics"],  # type: ignore[index]
            "trade_management_summary": _trade_management_summary_fixture(),
        },
        trade_records=[_minimal_trade(trade_management=_trade_management_block())],
    )
    payload["report_schema_version"] = 6

    report = parse_run_report(payload)
    variant = report.variants[0]
    trade = variant.trade_records[0]

    assert trade.trade_management is not None
    assert trade.trade_management.phase_at_exit == "runner"
    assert trade.trade_management.bars_to_runner == 4
    assert variant.trade_management_events is not None
    assert len(variant.trade_management_events) == 2
    assert variant.trade_management_events[0].event_type == "phase_changed"
    assert variant.trade_management_events[1].event_type == "exit_executed"
    assert variant.metrics.trade_management_summary is not None
    assert variant.metrics.trade_management_summary["runner_capture_summary"]["trade_count"] == 1


def _managed_trade_management_block(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        **_trade_management_block(
            exit_layer="exit_management",
            exit_rule_id="be_at_protected",
            exit_component_id="break_even_stop",
        ),
        "active_stop_at_exit": 100.0,
        "active_take_at_exit": "disable_initial_tp",
        "active_stop_component_id": "break_even_stop",
        "active_take_component_id": "take_profile_switch",
        "exit_candidate_type": "managed_stop",
        "managed_events": [
            _trade_management_event(
                event_type="active_stop_updated",
                rule_id="be_at_protected",
                component_id="break_even_stop",
                stop_price=100.0,
            ),
            _trade_management_event(
                event_type="exit_executed",
                from_phase="protected",
                to_phase=None,
                rule_id="be_at_protected",
                component_id="break_even_stop",
                metadata={"exit_layer": "exit_management"},
            ),
        ],
    }
    base.update(overrides)
    return base


def _managed_trade_management_summary_fixture() -> dict[str, object]:
    return {
        **_trade_management_summary_fixture(),
        "stop_management_breakdown": {
            "break_even_stop": {"trade_count": 1, "pnl": -1.0, "win_count": 0},
            "lock_profit_stop": {"trade_count": 1, "pnl": 2.0, "win_count": 1},
        },
        "take_management_breakdown": {
            "take_profile_switch": {"trade_count": 1, "pnl": 3.0, "win_count": 1},
        },
        "runtime_exit_breakdown": {
            "phase_runtime_exit": {"trade_count": 1, "pnl": 4.0, "win_count": 1},
        },
    }


def test_parse_run_report_preserves_managed_trade_management_fields() -> None:
    payload = _minimal_report_payload(
        trade_management_events=[
            _trade_management_event(),
            _trade_management_event(
                event_type="active_stop_updated",
                rule_id="be_at_protected",
                component_id="break_even_stop",
                stop_price=100.0,
            ),
            _trade_management_event(
                event_type="active_take_updated",
                rule_id="disable_initial_tp_at_runner",
                component_id="take_profile_switch",
                metadata={"action": "disable_initial_tp"},
            ),
            _trade_management_event(
                event_type="runtime_exit_triggered",
                rule_id="close_at_exhaustion",
                component_id="phase_runtime_exit",
            ),
            _trade_management_event(
                event_type="exit_rule_triggered",
                rule_id="be_at_protected",
                component_id="break_even_stop",
            ),
            _trade_management_event(
                event_type="exit_executed",
                from_phase="protected",
                to_phase=None,
                rule_id="be_at_protected",
                component_id="break_even_stop",
                metadata={"exit_layer": "exit_management"},
            ),
        ],
        metrics={
            **_minimal_report_payload()["variants"][0]["metrics"],  # type: ignore[index]
            "trade_management_summary": _managed_trade_management_summary_fixture(),
            "baseline_vs_managed_summary": baseline_vs_managed_summary_placeholder(),
        },
        trade_records=[_minimal_trade(trade_management=_managed_trade_management_block())],
    )
    payload["report_schema_version"] = 6

    report = parse_run_report(payload)
    variant = report.variants[0]
    trade = variant.trade_records[0]
    tm = trade.trade_management

    assert tm is not None
    assert tm.active_stop_at_exit == 100.0
    assert tm.active_take_at_exit == "disable_initial_tp"
    assert tm.active_stop_component_id == "break_even_stop"
    assert tm.active_take_component_id == "take_profile_switch"
    assert tm.exit_candidate_type == "managed_stop"
    assert tm.exit_layer == "exit_management"
    assert tm.managed_events is not None
    assert len(tm.managed_events) == 2
    assert tm.managed_events[0].event_type == "active_stop_updated"

    assert variant.trade_management_events is not None
    event_types = {event.event_type for event in variant.trade_management_events}
    assert event_types == {
        "phase_changed",
        "active_stop_updated",
        "active_take_updated",
        "runtime_exit_triggered",
        "exit_rule_triggered",
        "exit_executed",
    }

    summary = variant.metrics.trade_management_summary
    assert summary is not None
    assert "stop_management_breakdown" in summary
    assert "take_management_breakdown" in summary
    assert "runtime_exit_breakdown" in summary

    baseline = variant.metrics.baseline_vs_managed_summary
    assert baseline is not None
    assert baseline["saved_by_managed_stop"] == []
    assert baseline["exit_layer_transition_matrix"] == {}


_MANAGED_SMOKE_ARTIFACT = Path("research/results/latest.json")


@pytest.mark.skipif(
    not _MANAGED_SMOKE_ARTIFACT.is_file(),
    reason="Slice 6 managed smoke artifact not present",
)
def test_parse_managed_smoke_artifact_from_slice_6() -> None:
    report = parse_run_report(
        json.loads(_MANAGED_SMOKE_ARTIFACT.read_text(encoding="utf-8")),
    )
    variant = report.variants[0]
    managed_trades = [
        trade
        for trade in variant.trade_records
        if trade.trade_management is not None
    ]

    assert variant.trade_management_events
    assert variant.metrics.trade_management_summary is not None
    assert variant.metrics.baseline_vs_managed_summary is not None
    assert managed_trades
    sample = managed_trades[0].trade_management
    assert sample is not None
    assert sample.active_stop_at_exit is not None or sample.exit_candidate_type is not None
    assert sample.managed_events


def test_parse_run_summary_report_preserves_trade_management_summary_without_events() -> None:
    from research_api.services.results_reader import parse_run_summary_report

    variant = _minimal_report_payload()["variants"][0]
    assert isinstance(variant, dict)
    metrics = variant["metrics"]
    assert isinstance(metrics, dict)
    metrics["trade_management_summary"] = _trade_management_summary_fixture()
    compact_payload = {
        "run_id": "2026-01-01T000000Z_ema_pullback_BTCUSDT_5m_test",
        "created_at": "2026-01-01T00:00:00Z",
        "report_schema_version": 6,
        "family": "ema_pullback",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "data_range": {"from_open_time_ms": 1_000_000, "to_open_time_ms": 2_000_000},
        "variants_count": 1,
        "variants": [
            {
                **variant,
                "trade_records_count": 1,
                "closed_trades_count": 1,
                "open_trades_count": 0,
            }
        ],
        "artifact_kind": "run_summary",
        "summary_schema_version": 1,
        "source_report_path": "research/results/runs/2026-01-01T000000Z_ema_pullback_BTCUSDT_5m_test.json",
    }

    summary = parse_run_summary_report(compact_payload)
    compact_variant = summary.variants[0]

    assert summary.artifact_kind == "run_summary"
    assert compact_variant.metrics.trade_management_summary is not None
    assert compact_variant.metrics.trade_management_summary["phase_transition_counts"]["runner"] == 1
    assert not hasattr(compact_variant, "trade_management_events")
    assert compact_variant.trade_records_count == 1


def test_parse_run_summary_report_preserves_managed_metrics_without_events() -> None:
    from research_api.services.results_reader import parse_run_summary_report

    variant = _minimal_report_payload()["variants"][0]
    assert isinstance(variant, dict)
    metrics = variant["metrics"]
    assert isinstance(metrics, dict)
    metrics["trade_management_summary"] = _managed_trade_management_summary_fixture()
    metrics["baseline_vs_managed_summary"] = baseline_vs_managed_summary_placeholder()
    compact_payload = {
        "run_id": "2026-01-01T000000Z_ema_pullback_BTCUSDT_5m_managed",
        "created_at": "2026-01-01T00:00:00Z",
        "report_schema_version": 6,
        "family": "ema_pullback",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "data_range": {"from_open_time_ms": 1_000_000, "to_open_time_ms": 2_000_000},
        "variants_count": 1,
        "variants": [
            {
                **variant,
                "trade_records_count": 1,
                "closed_trades_count": 1,
                "open_trades_count": 0,
            }
        ],
        "artifact_kind": "run_summary",
        "summary_schema_version": 1,
        "source_report_path": "research/results/runs/2026-01-01T000000Z_ema_pullback_BTCUSDT_5m_managed.json",
    }
    compact_payload["variants"][0].pop("trade_records", None)
    compact_payload["variants"][0].pop("trade_management_events", None)

    summary = parse_run_summary_report(compact_payload)
    compact_variant = summary.variants[0]

    assert compact_variant.metrics.trade_management_summary is not None
    assert compact_variant.metrics.trade_management_summary["stop_management_breakdown"]["break_even_stop"][
        "trade_count"
    ] == 1
    assert compact_variant.metrics.baseline_vs_managed_summary is not None
    assert compact_variant.metrics.baseline_vs_managed_summary["runtime_exit_helped"] == []


def test_parse_run_report_accepts_exit_owner_on_trade_management() -> None:
    payload = _minimal_report_payload(
        trade_records=[
            _minimal_trade(
                trade_management=_trade_management_block(
                    exit_layer="exit_management.runtime_exit",
                    exit_owner="exit_management",
                ),
            ),
        ],
    )
    report = parse_run_report(payload)
    tm = report.variants[0].trade_records[0].trade_management
    assert tm is not None
    assert tm.exit_owner == "exit_management"
    assert tm.exit_layer == "exit_management.runtime_exit"


@pytest.mark.parametrize(
    "run_id",
    [
        "2026-06-09T132642Z_ema_pullback_BTCUSDT_5m__strict_adx40_runner_runtime_rsi90_ema100_200_smoke",
        "2026-06-09T133027Z_ema_pullback_BTCUSDT_5m__baseline_no_runtime",
    ],
)
def test_load_recent_managed_smoke_runs_from_disk(run_id: str) -> None:
    path = Path("research/results/runs") / f"{run_id}.json"
    if not path.is_file():
        pytest.skip(f"missing artifact {path}")
    report = parse_run_report(json.loads(path.read_text(encoding="utf-8")))
    assert report.run_id == run_id
    assert report.variants[0].trade_records
