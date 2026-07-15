"""Slice 2: managed runtime core — empty-array parity and skeleton types."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from research.strategies.ema_pullback.execution import backtest
from research.strategies.ema_pullback.execution.trade_runtime import (
    MANAGED_ACTIVE_LAYER_EVENT_TYPES,
    MANAGED_RUNTIME_EVENT_TYPES,
    ActiveManagementSnapshot,
    empty_active_management_snapshot,
    run_managed_exit_runtime,
    trade_management_events_payload,
)
from tests.phase_rule_test_helpers import make_phase_rule
from research.strategies.ema_pullback.spec import (
    ExitManagementSpec,
    empty_exit_management,
)
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec


def _series(values: list[float]) -> pd.Series:
    return pd.Series(
        values,
        index=pd.date_range("2024-01-01", periods=len(values), freq="h", tz="UTC"),
        dtype=float,
    )


def _ohlcv(periods: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="h", tz="UTC")
    close = pd.Series(range(100, 100 + periods), index=idx, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0,
        }
    )


def _managed_empty_exit_management() -> ExitManagementSpec:
    return ExitManagementSpec(
        mode="managed",
        phase_rules=(),
        stop_management=(),
        take_management=(),
        runtime_exits=(),
    )


def test_empty_active_management_snapshot_has_neutral_layers() -> None:
    snap = empty_active_management_snapshot()
    assert isinstance(snap, ActiveManagementSnapshot)
    assert snap.active_stop_price is None
    assert snap.active_stop_rule_id is None
    assert snap.active_stop_component_id is None
    assert snap.active_take_profile == "initial"
    assert snap.active_take_rule_id is None
    assert snap.active_take_component_id is None
    assert snap.active_runtime_exit_rules == ()


def test_managed_runtime_event_types_declared() -> None:
    assert "phase_changed" in MANAGED_RUNTIME_EVENT_TYPES
    assert "active_stop_updated" in MANAGED_RUNTIME_EVENT_TYPES
    assert "active_take_updated" in MANAGED_RUNTIME_EVENT_TYPES
    assert "runtime_exit_triggered" in MANAGED_RUNTIME_EVENT_TYPES
    assert "exit_rule_triggered" in MANAGED_RUNTIME_EVENT_TYPES
    assert "exit_executed" in MANAGED_RUNTIME_EVENT_TYPES


def test_managed_empty_arrays_emit_no_active_layer_events() -> None:
    high = _series([101.0, 103.0, 105.0, 104.0])
    low = _series([99.0, 98.0, 101.0, 100.0])
    close = _series([100.0, 102.0, 104.0, 103.0])
    open_ = close - 0.25

    result = run_managed_exit_runtime(
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
            }
        ],
        open_=open_,
        high=high,
        low=low,
        close=close,
        phase_rules=(
            make_phase_rule(
                "to_proven_after_2_bars",
                "proven",
                "bars_in_trade",
                {"threshold": 2},
            ),
        ),
    )

    state = result.states_by_trade_id["L1"]
    assert state.active_management == empty_active_management_snapshot()
    active_events = [
        event
        for event in result.events
        if event.event_type in MANAGED_ACTIVE_LAYER_EVENT_TYPES
    ]
    assert active_events == []
    phase_events = [event for event in result.events if event.event_type == "phase_changed"]
    assert len(phase_events) == 1
    assert result.events[-1].event_type == "exit_executed"
    payload = trade_management_events_payload(result)
    assert not any(
        item["event_type"] in MANAGED_ACTIVE_LAYER_EVENT_TYPES for item in payload
    )


@pytest.mark.optional_vectorbt
def test_managed_empty_arrays_parity_vs_baseline() -> None:
    pytest.importorskip("vectorbt")

    baseline = make_ema_pullback_strategy_spec()
    managed = replace(
        baseline,
        trade_management=replace(
            baseline.trade_management,
            exit_management=_managed_empty_exit_management(),
        ),
    )
    data = _ohlcv(120)

    baseline_result = backtest.run_strategy_spec(baseline, data)
    managed_result = backtest.run_strategy_spec(managed, data)

    assert managed_result.metrics.total.trades == baseline_result.metrics.total.trades
    assert managed_result.metrics.total.pnl == pytest.approx(baseline_result.metrics.total.pnl)
    if baseline_result.metrics.total.profit_factor is None:
        assert managed_result.metrics.total.profit_factor is None
    else:
        assert managed_result.metrics.total.profit_factor == pytest.approx(
            baseline_result.metrics.total.profit_factor
        )

    baseline_closed = [
        record for record in baseline_result.trade_records if record.get("status") == "closed"
    ]
    managed_closed = [
        record for record in managed_result.trade_records if record.get("status") == "closed"
    ]
    assert [record.get("exit_reason") for record in managed_closed] == [
        record.get("exit_reason") for record in baseline_closed
    ]
    assert [record.get("exit_idx") for record in managed_closed] == [
        record.get("exit_idx") for record in baseline_closed
    ]
    assert [record.get("exit_price") for record in managed_closed] == [
        record.get("exit_price") for record in baseline_closed
    ]

    managed_payload = managed_result.to_payload()
    assert "trade_management_events" in managed_payload
    assert not any(
        event.get("event_type") in MANAGED_ACTIVE_LAYER_EVENT_TYPES
        for event in managed_payload["trade_management_events"]
    )
    if managed_result.metrics.total.trades:
        assert "trade_management_summary" in managed_payload["metrics"]
        for record in managed_closed:
            assert isinstance(record.get("trade_management"), dict)
