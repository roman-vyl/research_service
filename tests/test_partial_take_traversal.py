"""`traverse_partial_takes` unit tests (`research-frozen-partial-take-
ladder-v1` task 4.1, design D1)."""

from __future__ import annotations

from decimal import Decimal

from research_service.domain.contracts import Candle
from research_service.domain.execution import EntryFill, PositionState
from research_service.execution.partial_takes import traverse_partial_takes
from research_service.execution.projection_entry import (
    resolve_initial_protection_from_opportunity,
)
from partial_take_harness import opportunity


def _position(side: str, legs) -> PositionState:
    fill = EntryFill(
        fill_id="entry",
        instance_id="i1",
        side=side,
        bar_index=0,
        time_ms=0,
        reference_price=Decimal("100"),
        fill_price=Decimal("100"),
        quantity=Decimal("100"),
        slippage_rate=Decimal("0"),
    )
    return PositionState(
        position_id="p1",
        instance_id="i1",
        side=side,
        entry_fill=fill,
        initial_protection=resolve_initial_protection_from_opportunity(
            opportunity(side, legs=legs), fill
        ),
    )


def _candle(open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(open_time_ms=300_000, open=open_, high=high, low=low, close=close, volume="1")


def _ids(reductions) -> list[str]:
    return [item.take_id for item in reductions]


def test_nearest_leg_first_regardless_of_wire_order() -> None:
    position = _position("long", [("far", 0.03, 0.25), ("near", 0.01, 0.25)])
    reductions = traverse_partial_takes(
        position, _candle("100", "104", "100", "100"), bar_index=1, filled_take_ids=(), final_level=None
    )
    assert _ids(reductions) == ["near", "far"]
    assert [item.fill_price for item in reductions] == [Decimal("101.00"), Decimal("103.00")]


def test_short_mirror_orders_downwards() -> None:
    position = _position("short", [("far", 0.03, 0.25), ("near", 0.01, 0.25)])
    reductions = traverse_partial_takes(
        position, _candle("100", "100", "96", "100"), bar_index=1, filled_take_ids=(), final_level=None
    )
    assert _ids(reductions) == ["near", "far"]
    assert [item.level for item in reductions] == [Decimal("99.00"), Decimal("97.00")]


def test_leg_strictly_beyond_final_is_dropped() -> None:
    position = _position("long", [("p1", 0.02, 0.25), ("p2", 0.06, 0.25)])
    reductions = traverse_partial_takes(
        position,
        _candle("100", "110", "100", "100"),
        bar_index=1,
        filled_take_ids=(),
        final_level=Decimal("104"),
    )
    assert _ids(reductions) == ["p1"]


def test_leg_at_final_level_is_kept() -> None:
    position = _position("long", [("at_final", 0.04, 0.25)])
    reductions = traverse_partial_takes(
        position,
        _candle("100", "110", "100", "100"),
        bar_index=1,
        filled_take_ids=(),
        final_level=Decimal("104.00"),
    )
    assert _ids(reductions) == ["at_final"]


def test_equal_leg_levels_keep_wire_order() -> None:
    position = _position("long", [("b", 0.01, 0.25), ("a", 0.01, 0.25)])
    reductions = traverse_partial_takes(
        position, _candle("100", "102", "100", "100"), bar_index=1, filled_take_ids=(), final_level=None
    )
    assert _ids(reductions) == ["b", "a"]


def test_already_filled_legs_are_skipped() -> None:
    position = _position("long", [("p1", 0.01, 0.25), ("p2", 0.03, 0.25)])
    reductions = traverse_partial_takes(
        position,
        _candle("100", "104", "100", "100"),
        bar_index=2,
        filled_take_ids={"p1"},
        final_level=None,
    )
    assert _ids(reductions) == ["p2"]


def test_bar_opening_beyond_a_leg_fills_at_the_level() -> None:
    position = _position("long", [("p1", 0.01, 0.25)])
    (reduction,) = traverse_partial_takes(
        position, _candle("102", "102.5", "101.5", "102"), bar_index=1, filled_take_ids=(), final_level=None
    )
    assert reduction.fill_price == reduction.level == Decimal("101.00")


def test_untouched_legs_and_entry_bar_produce_nothing() -> None:
    position = _position("long", [("p1", 0.01, 0.25)])
    assert traverse_partial_takes(
        position, _candle("100", "100.9", "99", "100"), bar_index=1, filled_take_ids=(), final_level=None
    ) == ()
    assert traverse_partial_takes(
        position, _candle("100", "120", "99", "100"), bar_index=0, filled_take_ids=(), final_level=None
    ) == ()


def test_reduction_facts() -> None:
    position = _position("long", [("p1", 0.01, 0.25)])
    (reduction,) = traverse_partial_takes(
        position, _candle("100", "102", "100", "100"), bar_index=3, filled_take_ids=(), final_level=None
    )
    assert reduction.fill_id == "reduce:p1:p1"
    assert (reduction.bar_index, reduction.time_ms) == (3, 300_000)
    assert (reduction.quantity, reduction.fraction_of_initial) == (Decimal("25.00"), Decimal("0.25"))
    assert reduction.attribution.exit_kind == "partial_take"
    assert reduction.attribution.component_id == "pct_partial_take"
