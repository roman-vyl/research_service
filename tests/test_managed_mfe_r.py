"""`mfe_r` trade metric (`mfe-r-phase-threshold-v1`): MFE in multiples of the
position's initial risk |reference entry - initial stop|, consumed
generically through `trade_metric` (never a component id)."""

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


def _position(side: str, stop: str | None) -> PositionState:
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
            stop_loss_price=None if stop is None else Decimal(stop),
        ),
    )


def _frame(side: str, n: int = 8) -> MarketFrame:
    # long: high of bar i is 101 + i; short: low of bar i is 99 - i.
    candles = tuple(
        Candle(
            open_time_ms=i * STEP,
            open=Decimal("100"),
            high=Decimal(str(101 + i)) if side == "long" else Decimal("100"),
            low=Decimal(str(99 - i)) if side == "short" else Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(n)
    )
    return MarketFrame(
        market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=n * STEP),
        candles=candles,
    )


def _projection(threshold_r: float, n: int = 8) -> HistoricalManagedProjectionDTO:
    return HistoricalManagedProjectionDTO(
        conditions={},
        distances={"to-proven:distance": tuple(threshold_r for _ in range(n))},
        rules=[
            {
                "kind": "phase_transition",
                "rule_id": "to-proven",
                "target_phase": "proven",
                "condition_id": None,
                "distance_id": "to-proven:distance",
                "trade_metric": "mfe_r",
            }
        ],
    )


def _phases(side: str, stop: str | None, threshold_r: float) -> list[str]:
    timeline = build_managed_policy_timeline_from_projection(
        _projection(threshold_r), _position(side, stop), _frame(side)
    )
    return [state.phase for state in timeline.states]


@pytest.mark.parametrize(
    ("side", "stop", "first_proven"),
    [
        # risk 2, 3R = 6 -> long high 101 + i >= 106 at bar 5; short mirrors.
        ("long", "98", 5),
        ("short", "102", 5),
        # risk 1, 3R = 3 -> bar 2.
        ("long", "99", 2),
        ("short", "101", 2),
    ],
)
def test_threshold_is_in_multiples_of_initial_risk(
    side: str, stop: str, first_proven: int
) -> None:
    phases = _phases(side, stop, 3.0)
    assert phases[:first_proven] == ["initial_risk"] * first_proven
    assert phases[first_proven] == "proven"


def test_without_initial_stop_the_metric_is_never_met() -> None:
    assert set(_phases("long", None, 0.5)) == {"initial_risk"}


def test_incremental_state_matches_the_eager_timeline() -> None:
    projection = _projection(3.0)
    position = _position("long", "98")
    frame = _frame("long")
    eager = build_managed_policy_timeline_from_projection(projection, position, frame)
    rule_set = ManagedRuleSet.from_projection(projection)
    state = initialize_managed_trade_state(position)
    phases: list[str] = []
    for index, candle in enumerate(frame.candles):
        last = index == len(frame.candles) - 1
        state, effective = advance_managed_trade_state(
            state,
            projection,
            rule_set,
            trade_id="trade-1",
            bar_index=index,
            source_time_ms=candle.open_time_ms,
            high=float(candle.high),
            low=float(candle.low),
            next_time_ms=None if last else frame.candles[index + 1].open_time_ms,
        )
        if effective is not None:
            phases.append(effective.phase)
    assert phases == [state_.phase for state_ in eager.states]
