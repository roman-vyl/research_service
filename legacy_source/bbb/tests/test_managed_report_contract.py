"""Slice 5: managed report serialization contract tests."""

from __future__ import annotations

import json

import pytest

from research.strategies.ema_pullback.execution.result_models import (
    OpenTradesBreakdown,
    SideMetrics,
    VariantMetrics,
    VariantResult,
)
from research.strategies.ema_pullback.execution.results import (
    baseline_vs_managed_summary_placeholder,
    build_managed_layer_breakdowns,
    build_research_run_payload,
    json_safe,
)
from research.strategies.ema_pullback.execution.trade_runtime import (
    ActiveManagementSnapshot,
    ManagedTradeRuntimeResult,
    ManagedTradeRuntimeState,
    TradeManagementEvent,
    TradeRuntimeState,
    apply_managed_trade_management_diagnostics,
    build_trade_management_summary,
    managed_trade_management_block_for_trade,
    trade_management_events_payload,
)


def _runtime_state(*, phase: str = "protected") -> TradeRuntimeState:
    return TradeRuntimeState(
        trade_id="long:0",
        side="long",
        entry_idx=0,
        entry_time_ms=0,
        entry_price=100.0,
        bars_in_trade=3,
        phase=phase,  # type: ignore[arg-type]
        max_phase_reached=phase,
        best_price=102.0,
        worst_price=99.0,
        mfe_price=102.0,
        mfe_pct=0.02,
        mae_price=99.0,
        mae_pct=0.01,
        active_stop_price=100.0,
        active_stop_source="managed",
        initial_stop_price=95.0,
        initial_take_profit_price=110.0,
        locked_exit_profile="neutral",
    )


def _managed_state(*, take_profile: str = "disable_initial_tp") -> ManagedTradeRuntimeState:
    return ManagedTradeRuntimeState(
        runtime=_runtime_state(),
        active_management=ActiveManagementSnapshot(
            active_stop_price=100.0,
            active_stop_rule_id="be",
            active_stop_component_id="break_even_stop",
            active_take_profile=take_profile,
            active_take_rule_id="disable_tp",
            active_take_component_id="take_profile_switch",
        ),
    )


def _exit_executed_event(*, layer: str, component_id: str) -> TradeManagementEvent:
    return TradeManagementEvent(
        trade_id="long:0",
        time_ms=1,
        bar_index=2,
        side="long",
        event_type="exit_executed",
        from_phase="protected",
        to_phase=None,
        rule_id="be",
        component_id=component_id,
        price=100.0,
        stop_price=100.0,
        mfe_pct=0.02,
        mae_pct=0.01,
        bars_in_trade=3,
        metadata={"exit_layer": layer, "exit_reason": f"{layer}:be"},
    )


def test_managed_trade_management_block_includes_managed_attribution_fields() -> None:
    record = {
        "trade_id": "long:0",
        "status": "closed",
        "exit_reason": "exit_management:be",
        "exit_instance_id": "be",
        "exit_component_id": "break_even_stop",
        "exit_layer": "exit_management",
        "managed_exit_candidate_type": "managed_stop",
        "pnl": 0.0,
        "exit_price": 100.0,
    }
    events = [
        TradeManagementEvent(
            trade_id="long:0",
            time_ms=1,
            bar_index=1,
            side="long",
            event_type="active_stop_updated",
            from_phase="protected",
            to_phase=None,
            rule_id="be",
            component_id="break_even_stop",
            price=100.0,
            stop_price=100.0,
            mfe_pct=0.02,
            mae_pct=0.01,
            bars_in_trade=2,
            metadata={"effective_from_bar": 2},
        ),
        _exit_executed_event(layer="exit_management", component_id="break_even_stop"),
    ]
    block = managed_trade_management_block_for_trade(
        record,
        _managed_state(),
        events,
    )

    assert block["phase_at_exit"] == "protected"
    assert block["active_stop_at_exit"] == 100.0
    assert block["active_take_at_exit"] == "disable_initial_tp"
    assert block["exit_layer"] == "exit_management"
    assert block["exit_rule_id"] == "be"
    assert block["exit_component_id"] == "break_even_stop"
    assert block["exit_candidate_type"] == "managed_stop"
    assert block["managed_events"][0]["event_type"] == "active_stop_updated"
    assert block["managed_events"][-1]["event_type"] == "exit_executed"


def test_build_managed_layer_breakdowns_groups_by_component_id() -> None:
    records = [
        {
            "status": "closed",
            "pnl": 1.0,
            "managed_exit_candidate_type": "managed_stop",
            "trade_management": {
                "exit_layer": "exit_management",
                "exit_component_id": "break_even_stop",
                "exit_candidate_type": "managed_stop",
                "active_take_component_id": "take_profile_switch",
                "active_take_at_exit": "disable_initial_tp",
            },
        },
        {
            "status": "closed",
            "pnl": -2.0,
            "managed_exit_candidate_type": "runtime_exit",
            "trade_management": {
                "exit_layer": "exit_management",
                "exit_component_id": "phase_runtime_exit",
                "exit_candidate_type": "runtime_exit",
            },
        },
    ]
    breakdowns = build_managed_layer_breakdowns(records)

    assert breakdowns["stop_management_breakdown"]["break_even_stop"]["trade_count"] == 1
    assert breakdowns["stop_management_breakdown"]["break_even_stop"]["pnl"] == pytest.approx(1.0)
    assert breakdowns["runtime_exit_breakdown"]["phase_runtime_exit"]["trade_count"] == 1
    assert breakdowns["take_management_breakdown"]["take_profile_switch"]["trade_count"] == 1


def test_build_trade_management_summary_managed_mode_adds_layer_breakdowns() -> None:
    records = [
        {
            "status": "closed",
            "pnl": 0.5,
            "exit_reason": "exit_management:be",
            "managed_exit_candidate_type": "managed_stop",
            "trade_management": {
                "phase_at_exit": "protected",
                "max_phase_reached": "protected",
                "exit_layer": "exit_management",
                "exit_component_id": "break_even_stop",
                "exit_candidate_type": "managed_stop",
                "mfe_pct": 0.02,
                "giveback_from_best_price_pct": 0.01,
                "capture_ratio": 0.5,
            },
        }
    ]
    summary = build_trade_management_summary(records, managed_mode=True)

    assert summary is not None
    assert summary["exit_layer_breakdown"] == {"exit_management": 1}
    assert "break_even_stop" in summary["stop_management_breakdown"]
    assert summary["take_management_breakdown"] == {}
    assert summary["runtime_exit_breakdown"] == {}


def test_diagnostic_summary_omits_managed_only_breakdown_sections() -> None:
    records = [
        {
            "status": "closed",
            "pnl": 1.0,
            "exit_reason": "signal:exit",
            "trade_management": {
                "phase_at_exit": "runner",
                "max_phase_reached": "runner",
                "exit_layer": "signal",
                "mfe_pct": 0.05,
                "giveback_from_best_price_pct": 0.01,
                "capture_ratio": 0.8,
            },
        }
    ]
    summary = build_trade_management_summary(records, managed_mode=False)

    assert summary is not None
    assert "stop_management_breakdown" not in summary
    assert "take_management_breakdown" not in summary
    assert "runtime_exit_breakdown" not in summary


def test_baseline_vs_managed_summary_placeholder_shape() -> None:
    placeholder = baseline_vs_managed_summary_placeholder()
    assert placeholder["saved_by_managed_stop"] == []
    assert placeholder["exit_layer_transition_matrix"] == {}


def test_variant_metrics_payload_includes_managed_summary_fields() -> None:
    metrics = VariantMetrics(
        long=SideMetrics(0, 0.0, 0.0, None, None),
        short=SideMetrics(0, 0.0, 0.0, None, None),
        total=SideMetrics(1, 1.0, 0.01, None, 1.0),
        sharpe=0.1,
        max_drawdown=-0.01,
        open_trades=OpenTradesBreakdown(0, 0, 0),
        trade_management_summary={
            "exit_layer_breakdown": {"exit_management": 1},
            "stop_management_breakdown": {"break_even_stop": {"trade_count": 1, "pnl": 0.0, "win_count": 0}},
            "take_management_breakdown": {},
            "runtime_exit_breakdown": {},
        },
        baseline_vs_managed_summary=baseline_vs_managed_summary_placeholder(),
    )
    payload = metrics.to_payload()

    assert payload["trade_management_summary"]["stop_management_breakdown"]["break_even_stop"]["trade_count"] == 1
    assert payload["baseline_vs_managed_summary"]["runtime_exit_helped"] == []


def test_variant_result_serializes_trade_management_events() -> None:
    result = VariantResult(
        variant="v1",
        config_id="cfg",
        symbol="BTCUSDT",
        timeframe="1h",
        strategy_spec={"variant": "v1"},
        metrics=VariantMetrics(
            long=SideMetrics(0, 0.0, 0.0, None, None),
            short=SideMetrics(0, 0.0, 0.0, None, None),
            total=SideMetrics(1, 1.0, 0.01, None, 1.0),
            sharpe=0.0,
            max_drawdown=0.0,
            open_trades=OpenTradesBreakdown(0, 0, 0),
        ),
        component_counters=[],
        trade_records=[],
        trade_management_events=[
            {"event_type": "active_stop_updated", "bar_index": 1, "component_id": "break_even_stop"},
            {"event_type": "exit_executed", "bar_index": 2, "metadata": {"exit_layer": "exit_management"}},
        ],
    )
    payload = result.to_payload()
    types = {item["event_type"] for item in payload["trade_management_events"]}
    assert types == {"active_stop_updated", "exit_executed"}


def test_legacy_report_without_managed_fields_still_round_trips() -> None:
    from datetime import datetime, timezone

    variant = {
        "variant": "v1",
        "config_id": "cfg",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "strategy_spec": {"variant": "v1"},
        "metrics": {
            "long": {"trades": 0, "pnl": 0.0, "return_pct": 0.0, "profit_factor": None, "win_rate": None},
            "short": {"trades": 0, "pnl": 0.0, "return_pct": 0.0, "profit_factor": None, "win_rate": None},
            "total": {
                "trades": 1,
                "pnl": 1.0,
                "return_pct": 0.01,
                "profit_factor": None,
                "win_rate": 1.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            },
            "open_trades": {"long": 0, "short": 0, "total": 0},
        },
        "component_counters": [],
        "trade_records": [
            {
                "trade_id": 1,
                "direction": "long",
                "status": "closed",
                "entry_time_ms": 1,
                "exit_time_ms": 2,
                "entry_price": 100.0,
                "exit_price": 101.0,
                "size": 1.0,
                "pnl": 1.0,
                "return_pct": 0.01,
                "exit_reason": "signal:exit",
            }
        ],
    }
    payload = build_research_run_payload(
        run_id="rid",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        family="ema_pullback",
        symbol="BTCUSDT",
        timeframe="1h",
        candles_count=10,
        data_range_from_ms=1,
        data_range_to_ms=2,
        variants=[variant],
    )
    raw = json.dumps(json_safe(payload))
    parsed = json.loads(raw)
    assert "trade_management_events" not in parsed["variants"][0]
    assert "baseline_vs_managed_summary" not in parsed["variants"][0]["metrics"]
    assert "trade_management" not in parsed["variants"][0]["trade_records"][0]


def test_apply_managed_diagnostics_attaches_block_to_closed_trade() -> None:
    record = {
        "trade_id": "long:0",
        "status": "closed",
        "direction": "long",
        "exit_reason": "exit_management:be",
        "exit_layer": "exit_management",
        "managed_exit_candidate_type": "managed_stop",
        "pnl": 0.0,
    }
    managed = ManagedTradeRuntimeResult(
        states_by_trade_id={"long:0": _managed_state()},
        events=[_exit_executed_event(layer="exit_management", component_id="break_even_stop")],
    )
    apply_managed_trade_management_diagnostics([record], managed)
    tm = record["trade_management"]
    assert tm["active_stop_at_exit"] == 100.0
    assert tm["exit_layer"] == "exit_management"
    assert len(tm["managed_events"]) == 1


def test_trade_management_events_payload_preserves_managed_event_types() -> None:
    managed = ManagedTradeRuntimeResult(
        states_by_trade_id={"long:0": _managed_state()},
        events=[
            TradeManagementEvent(
                trade_id="long:0",
                time_ms=1,
                bar_index=1,
                side="long",
                event_type="runtime_exit_triggered",
                from_phase="exhaustion",
                to_phase=None,
                rule_id="exit_ex",
                component_id="phase_runtime_exit",
                price=99.0,
                stop_price=None,
                mfe_pct=0.03,
                mae_pct=0.01,
                bars_in_trade=4,
                metadata={},
            ),
            _exit_executed_event(layer="exit_management", component_id="phase_runtime_exit"),
        ],
    )
    payload = trade_management_events_payload(managed)
    assert {item["event_type"] for item in payload} == {
        "runtime_exit_triggered",
        "exit_executed",
    }
