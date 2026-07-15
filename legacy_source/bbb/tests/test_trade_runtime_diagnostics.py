from __future__ import annotations

import pytest

pytest.importorskip("pandas")

import pandas as pd

from research.strategies.ema_pullback.execution.trade_runtime import (
    TradeRuntimeState,
    apply_trade_management_diagnostics,
    build_trade_management_summary,
    build_trade_runtime_diagnostics,
    evaluate_phase_rules,
    trade_management_events_payload,
)
from research.strategies.ema_pullback.phase_rule_conditions.registry import (
    PhaseRuleEvaluationContext,
)
from tests.phase_rule_test_helpers import make_phase_rule


def _series(values: list[float]) -> pd.Series:
    return pd.Series(
        values,
        index=pd.date_range("2024-01-01", periods=len(values), freq="h", tz="UTC"),
        dtype=float,
    )


def test_long_runtime_state_uses_favorable_high_and_adverse_low() -> None:
    high = _series([100.5, 103.0, 105.0, 104.0])
    low = _series([99.5, 98.0, 101.0, 100.0])
    close = _series([100.0, 102.0, 104.0, 103.0])
    result = build_trade_runtime_diagnostics(
        trade_records=[
            {
                "trade_id": "L1",
                "status": "closed",
                "direction": "long",
                "entry_idx": 1,
                "exit_idx": 3,
                "entry_price": 100.0,
                "exit_price": 103.0,
                "exit_reason": "signal:exit",
                "entry_profile": "aligned",
                "exit_component_id": "no_signal_exit",
            }
        ],
        high=high,
        low=low,
        close=close,
        phase_rules=(),
    )

    state = result.states_by_trade_id["L1"]
    assert state.bars_in_trade == 3
    assert state.best_price == 105.0
    assert state.worst_price == 98.0
    assert state.mfe_price == 105.0
    assert state.mae_price == 98.0
    assert state.mfe_pct == pytest.approx(0.05)
    assert state.mae_pct == pytest.approx(0.02)
    assert result.events[-1].event_type == "exit_executed"
    assert result.events[-1].component_id == "no_signal_exit"


def test_short_runtime_state_uses_favorable_low_and_adverse_high() -> None:
    high = _series([100.5, 103.0, 101.0, 104.0])
    low = _series([99.5, 97.0, 95.0, 96.0])
    close = _series([100.0, 98.0, 96.0, 97.0])
    result = build_trade_runtime_diagnostics(
        trade_records=[
            {
                "trade_id": "S1",
                "status": "closed",
                "direction": "short",
                "entry_idx": 1,
                "exit_idx": 3,
                "entry_price": 100.0,
                "exit_price": 97.0,
                "exit_reason": "take_profit:tp",
                "entry_profile": "countertrend",
            }
        ],
        high=high,
        low=low,
        close=close,
        phase_rules=(),
    )

    state = result.states_by_trade_id["S1"]
    assert state.bars_in_trade == 3
    assert state.best_price == 95.0
    assert state.worst_price == 104.0
    assert state.mfe_price == 95.0
    assert state.mae_price == 104.0
    assert state.mfe_pct == pytest.approx(0.05)
    assert state.mae_pct == pytest.approx(0.04)


def test_phase_rules_support_mfe_pct_bars_and_mfe_atr() -> None:
    high = _series([101.0, 102.0, 104.0, 106.0])
    low = _series([99.0, 100.0, 101.0, 102.0])
    close = _series([100.0, 101.0, 103.0, 105.0])
    atr = _series([2.0, 2.0, 2.0, 2.0])

    result = build_trade_runtime_diagnostics(
        trade_records=[
            {
                "trade_id": "T1",
                "status": "closed",
                "direction": "long",
                "entry_idx": 0,
                "exit_idx": 3,
                "entry_price": 100.0,
                "exit_price": 105.0,
                "exit_reason": "signal:exit",
            }
        ],
        high=high,
        low=low,
        close=close,
        phase_rules=(
            make_phase_rule(
                "to_proven_at_1atr",
                "proven",
                "mfe_atr",
                {
                    "threshold": 1.0,
                    "atr": {"timeframe": "base", "period": 14},
                },
            ),
            make_phase_rule(
                "to_protected_after_2_bars",
                "protected",
                "bars_in_trade",
                {"threshold": 2},
            ),
            make_phase_rule(
                "to_runner_at_5pct",
                "runner",
                "mfe_pct",
                {"threshold": 0.05},
            ),
        ),
        eval_context=PhaseRuleEvaluationContext(
            atr_series_by_key={("base", 14): atr},
            adx_dmi_series_by_key={},
        ),
    )

    phase_events = [event for event in result.events if event.event_type == "phase_changed"]
    assert [event.rule_id for event in phase_events] == [
        "to_proven_at_1atr",
        "to_protected_after_2_bars",
        "to_runner_at_5pct",
    ]
    assert [event.to_phase for event in phase_events] == ["proven", "protected", "runner"]
    assert result.states_by_trade_id["T1"].max_phase_reached == "runner"


def test_runtime_phase_evaluation_does_not_move_backwards() -> None:
    state = TradeRuntimeState(
        trade_id="T1",
        side="long",
        entry_idx=0,
        entry_time_ms=0,
        entry_price=100.0,
        bars_in_trade=5,
        phase="runner",
        max_phase_reached="runner",
        best_price=106.0,
        worst_price=99.0,
        mfe_price=106.0,
        mfe_pct=0.06,
        mae_price=99.0,
        mae_pct=-0.01,
        active_stop_price=None,
        active_stop_source=None,
        initial_stop_price=None,
        initial_take_profit_price=None,
        locked_exit_profile=None,
    )

    events = evaluate_phase_rules(
        state,
        (make_phase_rule("late_protected", "protected", "mfe_pct", {"threshold": 0.01}),),
        bar_index=4,
        time_ms=0,
    )

    assert events == []
    assert state.phase == "runner"
    assert state.max_phase_reached == "runner"


def test_open_trades_are_ignored_by_runtime_diagnostics() -> None:
    high = _series([101.0, 102.0])
    low = _series([99.0, 100.0])
    close = _series([100.0, 101.0])

    result = build_trade_runtime_diagnostics(
        trade_records=[
            {
                "trade_id": "O1",
                "status": "open",
                "direction": "long",
                "entry_idx": 0,
                "exit_idx": 1,
                "entry_price": 100.0,
            }
        ],
        high=high,
        low=low,
        close=close,
        phase_rules=(),
    )

    assert result.states_by_trade_id == {}
    assert result.events == []


def test_closed_runner_trade_serializes_trade_management_block_and_summary() -> None:
    high = _series([101.0, 102.0, 104.0, 106.0])
    low = _series([99.0, 100.0, 101.0, 102.0])
    close = _series([100.0, 101.0, 103.0, 105.0])
    trades = [
        {
            "trade_id": "1",
            "status": "closed",
            "direction": "long",
            "entry_idx": 0,
            "exit_idx": 3,
            "entry_price": 100.0,
            "exit_price": 105.0,
            "pnl": 5.0,
            "exit_reason": "signal:exit",
            "exit_kind": "signal",
            "exit_instance_id": "exit",
            "exit_component_id": "no_signal_exit",
        }
    ]
    result = build_trade_runtime_diagnostics(
        trade_records=trades,
        high=high,
        low=low,
        close=close,
        phase_rules=(
            make_phase_rule("to_proven_at_1pct", "proven", "mfe_pct", {"threshold": 0.01}),
            make_phase_rule(
                "to_protected_after_2_bars",
                "protected",
                "bars_in_trade",
                {"threshold": 2},
            ),
            make_phase_rule("to_runner_at_5pct", "runner", "mfe_pct", {"threshold": 0.05}),
        ),
    )

    apply_trade_management_diagnostics(trades, result)
    tm = trades[0]["trade_management"]

    assert tm["phase_at_exit"] == "runner"
    assert tm["max_phase_reached"] == "runner"
    assert tm["bars_to_proven"] == 1
    assert tm["bars_to_protected"] == 2
    assert tm["bars_to_runner"] == 4
    assert tm["mfe_at_runner_pct"] == pytest.approx(0.06)
    assert tm["exit_layer"] == "signal"
    assert tm["exit_rule_id"] == "exit"
    assert tm["exit_component_id"] == "no_signal_exit"
    assert tm["best_price_before_exit"] == 106.0
    assert tm["giveback_from_best_price_pct"] == pytest.approx(0.01)

    summary = build_trade_management_summary(trades)
    assert summary is not None
    runner_bucket = summary["by_phase_reached"]["runner"]
    assert runner_bucket["trade_count"] == 1
    assert runner_bucket["avg_mfe_pct"] == pytest.approx(0.06)
    assert summary["runner_capture_summary"]["trade_count"] == 1
    assert summary["runner_capture_summary"]["exit_layer_mix"] == {"signal": 1}
    assert summary["runner_capture_summary"]["old_exit_reason_mix"] == {"signal:exit": 1}


def test_initial_risk_trade_serializes_missing_milestones_as_null_not_zero() -> None:
    high = _series([100.5, 100.8])
    low = _series([99.0, 99.5])
    close = _series([100.0, 100.2])
    trades = [
        {
            "trade_id": "1",
            "status": "closed",
            "direction": "long",
            "entry_idx": 0,
            "exit_idx": 1,
            "entry_price": 100.0,
            "exit_price": 100.2,
            "pnl": 0.2,
            "exit_reason": "signal:exit",
        },
        {
            "trade_id": "2",
            "status": "open",
            "direction": "long",
            "entry_idx": 1,
            "exit_idx": 1,
            "entry_price": 100.2,
            "exit_price": None,
            "exit_reason": "open",
        },
    ]
    result = build_trade_runtime_diagnostics(
        trade_records=trades,
        high=high,
        low=low,
        close=close,
        phase_rules=(
            make_phase_rule("to_runner_at_5pct", "runner", "mfe_pct", {"threshold": 0.05}),
        ),
    )

    apply_trade_management_diagnostics(trades, result)
    tm = trades[0]["trade_management"]

    assert tm["phase_at_exit"] == "initial_risk"
    assert tm["max_phase_reached"] == "initial_risk"
    assert tm["bars_to_runner"] is None
    assert tm["mfe_at_runner_pct"] is None
    assert "trade_management" not in trades[1]


def test_trade_management_events_payload_is_sorted_and_v1_event_types_only() -> None:
    high = _series([101.0, 102.0])
    low = _series([99.0, 100.0])
    close = _series([100.0, 101.0])
    result = build_trade_runtime_diagnostics(
        trade_records=[
            {
                "trade_id": "1",
                "status": "closed",
                "direction": "long",
                "entry_idx": 0,
                "exit_idx": 1,
                "entry_price": 100.0,
                "exit_price": 101.0,
                "exit_reason": "signal:exit",
            }
        ],
        high=high,
        low=low,
        close=close,
        phase_rules=(
            make_phase_rule(
                "to_proven_after_1_bar",
                "proven",
                "bars_in_trade",
                {"threshold": 1},
            ),
        ),
    )

    payload = trade_management_events_payload(result)

    assert [event["event_type"] for event in payload] == ["phase_changed", "exit_executed"]
    assert [event["bar_index"] for event in payload] == [0, 1]
    assert "active_stop_updated" not in {event["event_type"] for event in payload}
    assert "exit_rule_triggered" not in {event["event_type"] for event in payload}
