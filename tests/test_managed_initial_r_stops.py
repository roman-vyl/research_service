"""Closed initial-R stop formulas consumed from Engine's managed projection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    Candle,
    HistoricalManagedProjectionDTO,
    MarketFrame,
    MarketRange,
)
from research_service.domain.execution import EntryFill, InitialProtection, PositionState
from research_service.execution.managed_policy import (
    ManagedRuleSet,
    advance_managed_trade_state,
    build_managed_policy_timeline_from_projection,
    initialize_managed_trade_state,
)

STEP = 300_000


def _position(side: str, stop: str | None = None) -> PositionState:
    if stop is None:
        stop = "98" if side == "long" else "102"
    return PositionState(
        position_id="trade-1",
        instance_id="instance-1",
        side=side,
        entry_fill=EntryFill(
            fill_id="entry-1",
            instance_id="instance-1",
            side=side,
            bar_index=0,
            time_ms=0,
            reference_price=Decimal("100"),
            fill_price=Decimal("100"),
            quantity=Decimal("1"),
            slippage_rate=Decimal("0"),
        ),
        initial_protection=InitialProtection(
            side=side,
            source_bar_index=0,
            source_time_ms=0,
            anchor_price=Decimal("100"),
            stop_loss_price=None if stop == "missing" else Decimal(stop),
        ),
    )


def _frame(side: str) -> MarketFrame:
    favorable = [10, 12, 14, 16, 23, 20, 20]
    candles = tuple(
        Candle(
            open_time_ms=index * STEP,
            open=Decimal("100"),
            high=Decimal(str(100 + move)) if side == "long" else Decimal("100"),
            low=Decimal("100") if side == "long" else Decimal(str(100 - move)),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for index, move in enumerate(favorable)
    )
    return MarketFrame(
        market=MarketRange(
            ticker="BTCUSDT.P",
            timeframe="5m",
            from_ms=0,
            to_ms=len(candles) * STEP,
        ),
        candles=candles,
    )


def _projection(*, legacy_distance: float | None = None) -> HistoricalManagedProjectionDTO:
    n = 7
    distances: dict[str, tuple[float, ...]] = {
        "trigger": (6.0,) * n,
        "lock": (4.0,) * n,
        "trail": (2.0,) * n,
    }
    rules: list[dict[str, object]] = []
    if legacy_distance is not None:
        distances["legacy"] = (legacy_distance,) * n
        rules.append(
            {
                "kind": "stop_action",
                "rule_id": "legacy",
                "activation_phase": "initial_risk",
                "distance_id": "legacy",
            }
        )
    rules.extend(
        [
            {
                "kind": "stop_action",
                "rule_id": "lock",
                "activation_phase": "initial_risk",
                "distance_id": "lock",
                "stop_formula": "initial_r_lock",
                "trigger_distance_id": "trigger",
            },
            {
                "kind": "stop_action",
                "rule_id": "trail",
                "activation_phase": "initial_risk",
                "distance_id": "trail",
                "stop_formula": "initial_r_trailing",
                "trigger_distance_id": "trigger",
            },
        ]
    )
    return HistoricalManagedProjectionDTO(conditions={}, distances=distances, rules=rules)


def _incremental(side: str, projection: HistoricalManagedProjectionDTO):
    position = _position(side)
    frame = _frame(side)
    state = initialize_managed_trade_state(position)
    rule_set = ManagedRuleSet.from_projection(projection)
    effective = []
    for index, candle in enumerate(frame.candles):
        state, item = advance_managed_trade_state(
            state,
            projection,
            rule_set,
            trade_id=position.position_id,
            bar_index=index,
            source_time_ms=candle.open_time_ms,
            high=float(candle.high),
            low=float(candle.low),
            next_time_ms=(
                frame.candles[index + 1].open_time_ms
                if index + 1 < len(frame.candles)
                else None
            ),
        )
        if item is not None:
            effective.append(item)
    return state, effective


@pytest.mark.parametrize(
    ("side", "expected"),
    [
        ("long", [None, "108.0", "110.0", "112.0", "119.0", "119.0"]),
        ("short", [None, "92.0", "90.0", "88.0", "81.0", "81.0"]),
    ],
)
def test_lock_then_true_trail_follow_monotonic_mfe(side: str, expected: list[str | None]) -> None:
    projection = _projection()
    position = _position(side)
    frame = _frame(side)
    eager = build_managed_policy_timeline_from_projection(projection, position, frame)
    final_state, incremental = _incremental(side, projection)

    eager_prices = [None if state.active_stop_price is None else str(state.active_stop_price) for state in eager.states]
    incremental_prices = [
        None if state.active_stop_price is None else str(state.active_stop_price)
        for state in incremental
    ]
    assert eager_prices == expected
    assert incremental_prices == expected
    assert [state.active_stop_rule_id for state in eager.states] == [
        None,
        "lock",
        "trail",
        "trail",
        "trail",
        "trail",
    ]
    assert final_state.initial_risk == 2.0


def test_initial_r_formulas_fail_closed_without_initial_stop() -> None:
    position = _position("long", "missing")
    timeline = build_managed_policy_timeline_from_projection(
        _projection(), position, _frame("long")
    )
    assert all(state.active_stop_price is None for state in timeline.states)


def test_existing_tighter_stop_keeps_price_and_attribution() -> None:
    projection = _projection(legacy_distance=9.0)
    timeline = build_managed_policy_timeline_from_projection(
        projection, _position("long"), _frame("long")
    )
    # At the 6R trigger the lock/trail both propose 108, below the already
    # active legacy 109. The non-tightening candidates must not relabel it.
    state = timeline.states[1]
    assert state.active_stop_price == Decimal("109.0")
    assert state.active_stop_rule_id == "legacy"


def test_trigger_decision_is_effective_only_on_next_bar() -> None:
    timeline = build_managed_policy_timeline_from_projection(
        _projection(), _position("long"), _frame("long")
    )
    triggered = timeline.states[1]
    assert triggered.source_bar_index == 1
    assert triggered.effective_time_ms == 2 * STEP
    assert triggered.active_stop_price == Decimal("108.0")
