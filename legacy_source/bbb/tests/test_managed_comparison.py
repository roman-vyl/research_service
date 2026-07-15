"""Slice 9: baseline vs managed paired-run comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.strategies.ema_pullback.execution.managed_comparison import (
    apply_baseline_vs_managed_comparison_to_report,
    baseline_vs_managed_summary_placeholder,
    build_baseline_vs_managed_summary,
    derive_break_even_stop_view,
    exit_layer_for_record,
    trade_pair_key,
)


def _closed_trade(
    *,
    trade_id: int | str,
    direction: str = "long",
    entry_idx: int = 10,
    pnl: float = 0.0,
    exit_layer: str | None = None,
    exit_reason: str = "stop_loss:sl",
    exit_kind: str | None = "stop_loss",
    trade_management: dict | None = None,
    managed_exit_candidate_type: str | None = None,
) -> dict:
    record: dict = {
        "trade_id": trade_id,
        "direction": direction,
        "status": "closed",
        "entry_time_ms": entry_idx * 60_000,
        "exit_time_ms": entry_idx * 60_000 + 30_000,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "size": 1.0,
        "pnl": pnl,
        "return_pct": pnl / 100.0,
        "exit_reason": exit_reason,
        "entry_idx": entry_idx,
        "exit_idx": entry_idx + 1,
    }
    if exit_kind is not None:
        record["exit_kind"] = exit_kind
    if exit_layer is not None:
        record["exit_layer"] = exit_layer
    if managed_exit_candidate_type is not None:
        record["managed_exit_candidate_type"] = managed_exit_candidate_type
    if trade_management is not None:
        record["trade_management"] = trade_management
    return record


def test_trade_pair_key_uses_direction_and_entry_idx() -> None:
    assert trade_pair_key(_closed_trade(trade_id=1, direction="short", entry_idx=979)) == "short:979"
    assert trade_pair_key(_closed_trade(trade_id="short:979", direction="short", entry_idx=979)) == "short:979"


def test_build_baseline_vs_managed_summary_managed_stop_saved_and_hurt() -> None:
    baseline = [
        _closed_trade(trade_id=1, entry_idx=10, pnl=-5.0, exit_layer="exit_policy"),
    ]
    managed_saved = _closed_trade(
        trade_id="long:10",
        entry_idx=10,
        pnl=0.0,
        exit_layer="exit_management",
        exit_reason="exit_management:be",
        exit_kind=None,
        managed_exit_candidate_type="managed_stop",
        trade_management={
            "exit_layer": "exit_management",
            "exit_component_id": "break_even_stop",
            "exit_candidate_type": "managed_stop",
        },
    )
    managed_hurt = _closed_trade(
        trade_id="long:11",
        entry_idx=11,
        pnl=-2.0,
        exit_layer="exit_management",
        exit_reason="exit_management:lock",
        exit_kind=None,
        managed_exit_candidate_type="managed_stop",
        trade_management={
            "exit_layer": "exit_management",
            "exit_component_id": "lock_profit_stop",
            "exit_candidate_type": "managed_stop",
        },
    )
    baseline.append(_closed_trade(trade_id=2, entry_idx=11, pnl=1.0, exit_layer="exit_policy"))

    summary = build_baseline_vs_managed_summary(baseline, [managed_saved, managed_hurt])

    assert len(summary["saved_by_managed_stop"]) == 1
    assert summary["saved_by_managed_stop"][0]["pair_key"] == "long:10"
    assert summary["saved_by_managed_stop"][0]["pnl_delta"] == 5.0
    assert len(summary["hurt_by_managed_stop"]) == 1
    assert summary["hurt_by_managed_stop"][0]["pair_key"] == "long:11"
    assert summary["hurt_by_managed_stop"][0]["pnl_delta"] == -3.0


def test_build_baseline_vs_managed_summary_take_disabled_categories() -> None:
    baseline = [_closed_trade(trade_id=1, entry_idx=20, pnl=1.0)]
    managed_won = _closed_trade(
        trade_id="long:20",
        entry_idx=20,
        pnl=3.0,
        exit_layer="exit_management",
        exit_reason="exit_management:tp_disabled",
        exit_kind=None,
        trade_management={
            "exit_layer": "exit_management",
            "active_take_at_exit": "disable_initial_tp",
            "active_take_component_id": "take_profile_switch",
        },
    )
    managed_lost = _closed_trade(
        trade_id="long:21",
        entry_idx=21,
        pnl=-4.0,
        exit_layer="exit_management",
        exit_reason="exit_management:tp_disabled",
        exit_kind=None,
        trade_management={
            "exit_layer": "exit_management",
            "active_take_at_exit": "disable_initial_tp",
        },
    )
    baseline.append(_closed_trade(trade_id=2, entry_idx=21, pnl=2.0))

    summary = build_baseline_vs_managed_summary(
        baseline,
        [managed_won, managed_lost],
    )

    assert len(summary["take_disabled_then_won"]) == 1
    assert summary["take_disabled_then_won"][0]["active_take_at_exit"] == "disable_initial_tp"
    assert len(summary["take_disabled_then_lost"]) == 1


def test_build_baseline_vs_managed_summary_runtime_exit_helped_hurt() -> None:
    baseline = [
        _closed_trade(trade_id=1, entry_idx=30, pnl=-1.0),
        _closed_trade(trade_id=2, entry_idx=31, pnl=2.0),
    ]
    managed = [
        _closed_trade(
            trade_id="long:30",
            entry_idx=30,
            pnl=2.0,
            exit_layer="exit_management",
            exit_reason="exit_management:runtime",
            exit_kind=None,
            managed_exit_candidate_type="runtime_exit",
            trade_management={
                "exit_layer": "exit_management",
                "exit_component_id": "phase_runtime_exit",
                "exit_candidate_type": "runtime_exit",
            },
        ),
        _closed_trade(
            trade_id="long:31",
            entry_idx=31,
            pnl=0.0,
            exit_layer="exit_management",
            exit_reason="exit_management:runtime",
            exit_kind=None,
            managed_exit_candidate_type="runtime_exit",
            trade_management={
                "exit_component_id": "phase_runtime_exit",
                "exit_candidate_type": "runtime_exit",
            },
        ),
    ]

    summary = build_baseline_vs_managed_summary(baseline, managed)

    assert len(summary["runtime_exit_helped"]) == 1
    assert summary["runtime_exit_helped"][0]["pair_key"] == "long:30"
    assert len(summary["runtime_exit_hurt"]) == 1
    assert summary["runtime_exit_hurt"][0]["pair_key"] == "long:31"


def test_exit_layer_transition_matrix_covers_exit_policy_to_exit_management() -> None:
    baseline = [_closed_trade(trade_id=1, entry_idx=40, pnl=1.0, exit_layer="exit_policy")]
    managed = [
        _closed_trade(
            trade_id="long:40",
            entry_idx=40,
            pnl=0.5,
            exit_layer="exit_management",
            exit_kind=None,
            managed_exit_candidate_type="managed_stop",
            trade_management={"exit_layer": "exit_management"},
        )
    ]

    matrix = build_baseline_vs_managed_summary(baseline, managed)["exit_layer_transition_matrix"]

    assert matrix["exit_policy->exit_management"] == 1


def test_unpaired_managed_trades_are_ignored() -> None:
    summary = build_baseline_vs_managed_summary(
        [],
        [_closed_trade(trade_id="long:99", entry_idx=99, pnl=1.0)],
    )
    assert summary == baseline_vs_managed_summary_placeholder()


def test_derive_break_even_stop_view_from_stop_management_breakdown() -> None:
    view = derive_break_even_stop_view(
        {
            "break_even_stop": {"trade_count": 3, "pnl": -2.5, "win_count": 1},
            "lock_profit_stop": {"trade_count": 2, "pnl": 1.0, "win_count": 2},
        }
    )
    assert view == {"trade_count": 3, "pnl": -2.5, "win_count": 1}


def test_be_helped_hurt_derivable_without_schema_fields() -> None:
    summary = build_baseline_vs_managed_summary(
        [_closed_trade(trade_id=1, entry_idx=50, pnl=-3.0)],
        [
            _closed_trade(
                trade_id="long:50",
                entry_idx=50,
                pnl=0.0,
                exit_layer="exit_management",
                exit_kind=None,
                managed_exit_candidate_type="managed_stop",
                trade_management={
                    "exit_component_id": "break_even_stop",
                    "exit_candidate_type": "managed_stop",
                },
            )
        ],
    )
    be_saved = [
        item
        for item in summary["saved_by_managed_stop"]
        if item.get("managed_exit_component_id") == "break_even_stop"
    ]
    assert len(be_saved) == 1
    breakdown_view = derive_break_even_stop_view(
        {"break_even_stop": {"trade_count": 1, "pnl": 0.0, "win_count": 0}}
    )
    assert breakdown_view["trade_count"] == 1


def test_apply_baseline_vs_managed_comparison_to_report_populates_managed_metrics() -> None:
    managed_report = {
        "variants": [
            {
                "variant": "managed_v",
                "metrics": {"baseline_vs_managed_summary": baseline_vs_managed_summary_placeholder()},
                "trade_records": [
                    _closed_trade(
                        trade_id="long:10",
                        entry_idx=10,
                        pnl=0.0,
                        exit_layer="exit_management",
                        exit_kind=None,
                        managed_exit_candidate_type="managed_stop",
                    )
                ],
            }
        ]
    }
    baseline_report = {
        "variants": [
            {
                "variant": "baseline_v",
                "trade_records": [_closed_trade(trade_id=1, entry_idx=10, pnl=-2.0)],
            }
        ]
    }

    updated = apply_baseline_vs_managed_comparison_to_report(
        managed_report,
        baseline_report,
        managed_variant="managed_v",
        baseline_variant="baseline_v",
    )
    summary = updated["variants"][0]["metrics"]["baseline_vs_managed_summary"]
    assert len(summary["saved_by_managed_stop"]) == 1
    assert summary["exit_layer_transition_matrix"]["exit_policy->exit_management"] == 1


@pytest.mark.skipif(
    not Path("research/results/latest.json").is_file(),
    reason="managed smoke artifact not present",
)
def test_compare_smoke_artifacts_when_diagnostic_baseline_available() -> None:
    diagnostic_runs = sorted(Path("research/results/runs").glob("*diagnostic*smoke*.json"))
    managed_path = Path("research/results/latest.json")
    if not diagnostic_runs:
        pytest.skip("diagnostic smoke run artifact not present")

    baseline_report = json.loads(diagnostic_runs[-1].read_text(encoding="utf-8"))
    managed_report = json.loads(managed_path.read_text(encoding="utf-8"))
    updated = apply_baseline_vs_managed_comparison_to_report(managed_report, baseline_report)
    summary = updated["variants"][0]["metrics"]["baseline_vs_managed_summary"]
    matrix = summary["exit_layer_transition_matrix"]
    assert isinstance(matrix, dict)
    assert sum(matrix.values()) > 0
