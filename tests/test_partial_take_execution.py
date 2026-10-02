"""Partial take ladder on the projection loop
(`research-frozen-partial-take-ladder-v1` tasks 4.2-4.3,
`research-partial-take-execution-v1`).

Prices follow master plan §7: Q0 100, entry 100, stop 95/105, legs
101/103 (long) and 99/97 (short) at 25% each, final 108/92.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.accounting import AccountingPolicy
from research_service.accounting.service import account_execution_loop
from partial_take_harness import (
    D,
    FLAT,
    fills,
    frame,
    managed_projection,
    run,
)

_PROVEN = {
    "kind": "phase_transition",
    "rule_id": "to_proven",
    "target_phase": "proven",
    "condition_id": "always",
    "distance_id": None,
    "trade_metric": None,
}


def _disable_tp(bar_count: int):
    return managed_projection(
        [
            _PROVEN,
            {
                "kind": "take_action",
                "rule_id": "tp_off",
                "activation_phase": "proven",
                "resulting_profile": "disable_initial_tp",
            },
        ],
        bar_count=bar_count,
        conditions={"always": {0}},
    )


def _break_even_stop(bar_count: int):
    return managed_projection(
        [
            _PROVEN,
            {"kind": "stop_action", "rule_id": "be", "activation_phase": "proven", "distance_id": "zero"},
        ],
        bar_count=bar_count,
        conditions={"always": {0}},
        distances={"zero": 0.0},
    )


# --- master plan §7 truth table, rows 1-16, both sides --------------------

_P13 = (("p1", 0.02, 0.25), ("p2", 0.06, 0.25), ("p3", 0.08, 0.25))  # row 14 legs
_P_BEYOND = (("p", 0.10, 0.25),)  # rows 15-16 leg beyond the final take

TRUTH_TABLE = [
    # row, side, bars after entry, kwargs, expected fills, final status
    (1, "long", [("100", "100.8", "99", "100")], {}, [], "open"),
    (1, "short", [("100", "101", "99.2", "100")], {}, [], "open"),
    (2, "long", [("100", "101.5", "99.5", "100")], {}, [(1, "tp1", "101.00", "25.00")], "open"),
    (2, "short", [("100", "100.5", "98.5", "100")], {}, [(1, "tp1", "99.00", "25.00")], "open"),
    (
        3, "long", [("100", "104", "99.5", "100")], {},
        [(1, "tp1", "101.00", "25.00"), (1, "tp2", "103.00", "25.00")], "open",
    ),
    (
        3, "short", [("100", "100.5", "96", "100")], {},
        [(1, "tp1", "99.00", "25.00"), (1, "tp2", "97.00", "25.00")], "open",
    ),
    (
        4, "long", [("100", "109", "99.5", "100")], {},
        [(1, "tp1", "101.00", "25.00"), (1, "tp2", "103.00", "25.00"), (1, "take_profit", "108.00", "50.00")],
        "closed",
    ),
    (
        4, "short", [("100", "100.5", "91", "100")], {},
        [(1, "tp1", "99.00", "25.00"), (1, "tp2", "97.00", "25.00"), (1, "take_profit", "92.00", "50.00")],
        "closed",
    ),
    (5, "long", [("100", "102", "94", "100")], {}, [(1, "stop_loss", "95.00", "100")], "closed"),
    (5, "short", [("100", "106", "98", "100")], {}, [(1, "stop_loss", "105.00", "100")], "closed"),
    (6, "long", [("100", "110", "94", "100")], {}, [(1, "stop_loss", "95.00", "100")], "closed"),
    (6, "short", [("100", "106", "90", "100")], {}, [(1, "stop_loss", "105.00", "100")], "closed"),
    (
        7, "long", [("100", "101.5", "99.5", "100"), ("100", "109", "99.5", "100")], {},
        [(1, "tp1", "101.00", "25.00"), (2, "tp2", "103.00", "25.00"), (2, "take_profit", "108.00", "50.00")],
        "closed",
    ),
    (
        7, "short", [("100", "100.5", "98.5", "100"), ("100", "100.5", "91", "100")], {},
        [(1, "tp1", "99.00", "25.00"), (2, "tp2", "97.00", "25.00"), (2, "take_profit", "92.00", "50.00")],
        "closed",
    ),
    (
        8, "long", [("100", "101.5", "99.5", "100"), ("100", "102", "99.5", "101.8")],
        {"signal_bars": (2,)},
        [(1, "tp1", "101.00", "25.00"), (2, "signal", "101.8", "75.00")], "closed",
    ),
    (
        8, "short", [("100", "100.5", "98.5", "100"), ("100", "100.5", "98", "98.2")],
        {"signal_bars": (2,)},
        [(1, "tp1", "99.00", "25.00"), (2, "signal", "98.2", "75.00")], "closed",
    ),
    (
        9, "long", [("100", "101.5", "99.5", "100"), ("100", "100", "94", "95")], {},
        [(1, "tp1", "101.00", "25.00"), (2, "stop_loss", "95.00", "75.00")], "closed",
    ),
    (
        9, "short", [("100", "100.5", "98.5", "100"), ("100", "106", "100", "105")], {},
        [(1, "tp1", "99.00", "25.00"), (2, "stop_loss", "105.00", "75.00")], "closed",
    ),
    (
        10, "long", [("100", "101.5", "99.5", "100.7")], {"signal_bars": (1,)},
        [(1, "tp1", "101.00", "25.00"), (1, "signal", "100.7", "75.00")], "closed",
    ),
    (
        10, "short", [("100", "100.5", "98.5", "99.3")], {"signal_bars": (1,)},
        [(1, "tp1", "99.00", "25.00"), (1, "signal", "99.3", "75.00")], "closed",
    ),
    (
        11, "long", [("100", "110", "99.5", "100"), FLAT], {"managed": _disable_tp(3)},
        [(1, "tp1", "101.00", "25.00"), (1, "tp2", "103.00", "25.00")], "open",
    ),
    (
        11, "short", [("100", "100.5", "90", "100"), FLAT], {"managed": _disable_tp(3)},
        [(1, "tp1", "99.00", "25.00"), (1, "tp2", "97.00", "25.00")], "open",
    ),
    (12, "long", [FLAT], {"entry_bar": ("100", "120", "99", "100")}, [], "open"),
    (12, "short", [FLAT], {"entry_bar": ("100", "101", "80", "100")}, [], "open"),
    (13, "long", [("100", "109", "99.5", "100")], {"legs": ()}, [(1, "take_profit", "108.00", "100")], "closed"),
    (13, "short", [("100", "100.5", "91", "100")], {"legs": ()}, [(1, "take_profit", "92.00", "100")], "closed"),
    (
        14, "long", [("100", "110", "99.5", "100")], {"legs": _P13, "take": 0.04},
        [(1, "p1", "102.00", "25.00"), (1, "take_profit", "104.00", "75.00")], "closed",
    ),
    (
        14, "short", [("100", "100.5", "90", "100")], {"legs": _P13, "take": 0.04},
        [(1, "p1", "98.00", "25.00"), (1, "take_profit", "96.00", "75.00")], "closed",
    ),
    (15, "long", [("100", "107", "99.5", "100")], {"legs": _P_BEYOND}, [], "open"),
    (15, "short", [("100", "100.5", "93", "100")], {"legs": _P_BEYOND}, [], "open"),
    (16, "long", [("100", "115", "99.5", "100")], {"legs": _P_BEYOND}, [(1, "take_profit", "108.00", "100")], "closed"),
    (16, "short", [("100", "100.5", "85", "100")], {"legs": _P_BEYOND}, [(1, "take_profit", "92.00", "100")], "closed"),
]


@pytest.mark.parametrize(
    ("row", "side", "bars", "kwargs", "expected", "status"),
    TRUTH_TABLE,
    ids=[f"row{row}-{side}" for row, side, *_ in TRUTH_TABLE],
)
def test_master_plan_truth_table(row, side, bars, kwargs, expected, status) -> None:
    result = run(side, bars, **kwargs)
    assert fills(result) == [(bar, kind, D(price), D(qty)) for bar, kind, price, qty in expected], row
    assert result.positions[0].status == status, row


# --- spec scenarios not covered by a table row ---------------------------


def test_leg_at_the_final_level_fills_first_at_the_same_price() -> None:
    result = run("long", [("100", "109", "99.5", "100")], legs=(("at_final", 0.08, 0.25),))
    assert fills(result) == [
        (1, "at_final", D("108.00"), D("25.00")),
        (1, "take_profit", D("108.00"), D("75.00")),
    ]


def test_bar_opening_beyond_legs_and_final_fills_every_level_exactly() -> None:
    result = run("long", [("112", "113", "111", "112")], legs=(("tp", 0.03, 0.25),))
    assert fills(result) == [
        (1, "tp", D("103.00"), D("25.00")),
        (1, "take_profit", D("108.00"), D("75.00")),
    ]


def test_managed_stop_on_a_bar_touching_a_leg_closes_everything() -> None:
    result = run("long", [("100.5", "102", "99.5", "100.5"), FLAT], managed=_break_even_stop(3))
    assert fills(result) == [(1, "managed_stop", D("100.0"), D("100"))]
    assert result.positions[0].reductions == ()


def test_entry_bar_touching_every_level_then_a_later_bar_fills_legs() -> None:
    result = run(
        "long",
        [("100", "101.5", "99.5", "100")],
        entry_bar=("100", "120", "99", "100"),
    )
    assert fills(result) == [(1, "tp1", D("101.00"), D("25.00"))]


def test_reductions_belong_to_the_closed_position_in_order() -> None:
    result = run("long", [("100", "101.5", "99.5", "100"), ("100", "104", "99.5", "100"), ("100", "100", "94", "95")])
    (execution,) = result.positions
    assert [item.take_id for item in execution.reductions] == ["tp1", "tp2"]
    assert [item.bar_index for item in execution.reductions] == [1, 2]
    assert execution.remaining_quantity == Decimal("50.00")
    assert execution.exit_fill is not None and execution.exit_fill.candidate_type == "stop_loss"


def test_open_position_keeps_its_reductions() -> None:
    result = run("long", [("100", "101.5", "99.5", "100")])
    (execution,) = result.positions
    assert execution.status == "open"
    assert [item.take_id for item in execution.reductions] == ["tp1"]
    assert execution.remaining_quantity == Decimal("75.00")


# --- events (task 5.1-5.2, design D6-D7) ----------------------------------


def _event_rows(result):
    return [(event.bar_index, event.event_type, event.fill_id) for event in result.events]


def test_leg_and_final_on_one_bar_emit_reduced_before_exit() -> None:
    result = run("long", [("100", "109", "99.5", "100")])
    position_id = result.positions[0].position.position_id
    assert [(bar, kind) for bar, kind, _ in _event_rows(result)] == [
        (0, "entry_filled"),
        (1, "position_reduced"),
        (1, "position_reduced"),
        (1, "exit_filled"),
    ]
    assert [fill_id for _, kind, fill_id in _event_rows(result) if kind == "position_reduced"] == [
        f"reduce:{position_id}:tp1",
        f"reduce:{position_id}:tp2",
    ]
    assert result.events[1].event_id == f"event:reduce:{position_id}:tp1"


def test_reduction_event_metadata() -> None:
    result = run("long", [("100", "104", "99.5", "100")])
    first, second = (event for event in result.events if event.event_type == "position_reduced")
    assert first.metadata == {
        "take_id": "tp1",
        "level": "101.00",
        "fill_price": "101.00",
        "quantity": "25.00",
        "fraction_of_initial": "0.25",
        "remaining_quantity": "75.00",
        "rule_id": "tp1",
        "component_id": "pct_partial_take",
        "exit_kind": "partial_take",
        "locked_exit_profile": "aligned",
    }
    assert second.metadata["remaining_quantity"] == "50.00"
    assert second.metadata["level"] == "103.00"


def test_entry_filled_lists_legs_only_when_present() -> None:
    with_legs = run("short", [FLAT])
    assert with_legs.events[0].metadata["partial_takes"] == [
        {"take_id": "tp1", "level": "99.00", "quantity": "25.00", "fraction_of_initial": "0.25"},
        {"take_id": "tp2", "level": "97.00", "quantity": "25.00", "fraction_of_initial": "0.25"},
    ]
    without_legs = run("short", [FLAT], legs=())
    assert set(without_legs.events[0].metadata) == {
        "reference_price",
        "fill_price",
        "quantity",
        "stop_loss_price",
        "take_profit_price",
        "locked_exit_profile",
    }


def test_range_end_after_a_leg_reports_reduction_and_left_open_without_a_trade() -> None:
    bars = [FLAT, ("100", "101.5", "99.5", "100")]
    result = run("long", bars[1:])
    assert [event.event_type for event in result.events] == [
        "entry_filled",
        "position_reduced",
        "position_left_open",
    ]
    accounting = account_execution_loop(
        result, frame(bars), AccountingPolicy(initial_equity=Decimal("100000"))
    )
    assert accounting.trades == ()
    assert accounting.final_equity == Decimal("100000")
    assert accounting.open_position_count == 1
