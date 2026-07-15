"""Precise exit_layer / exit_owner attribution in reports."""

from __future__ import annotations

from research.strategies.ema_pullback.execution.results import build_managed_layer_breakdowns
from research.strategies.ema_pullback.execution.trade_runtime import (
    apply_managed_trade_management_diagnostics,
    build_trade_management_summary,
)


def test_runtime_exit_layer_breakdown_matches_trade_record() -> None:
    records = [
        {
            "trade_id": "L1",
            "status": "closed",
            "pnl": 5.0,
            "exit_layer": "exit_management.runtime_exit",
            "exit_owner": "exit_management",
            "managed_exit_candidate_type": "runtime_take",
            "trade_management": {
                "exit_layer": "exit_management.runtime_exit",
                "exit_owner": "exit_management",
                "exit_component_id": "rsi_signal_exit",
                "exit_candidate_type": "runtime_take",
                "max_phase_reached": "runner",
            },
        },
        {
            "trade_id": "L2",
            "status": "closed",
            "pnl": -2.0,
            "exit_layer": "exit_policy",
            "exit_owner": "exit_policy",
            "trade_management": {
                "exit_layer": "exit_policy",
                "exit_owner": "exit_policy",
                "max_phase_reached": "initial_risk",
            },
        },
    ]
    summary = build_trade_management_summary(records, managed_mode=True)
    assert summary is not None
    breakdown = summary["exit_layer_breakdown"]
    assert breakdown.get("exit_management.runtime_exit") == 1
    assert breakdown.get("exit_policy") == 1
    runtime = summary["runtime_exit_breakdown"]
    assert runtime["rsi_signal_exit"]["trade_count"] == 1
