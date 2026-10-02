"""Frozen partial take traversal (`research-frozen-partial-take-ladder-v1`
design D1, `research-partial-take-execution-v1`).

Pure. Called by the projection loop only on a bar after the entry bar
that has no stop or managed-stop candidate (stop wins without take
traversal). Returns this bar's partial take fills in price order away
from entry; the final take, when touched, is not filled here: it closes
the remainder through the existing `take_profit` candidate and its
arbitration priority, which ends the traversal.
"""

from __future__ import annotations

from collections.abc import Collection
from decimal import Decimal

from research_service.domain.contracts import Candle
from research_service.domain.execution import (
    PositionReduction,
    PositionState,
    ResolvedPartialTake,
)


def traverse_partial_takes(
    position: PositionState,
    candle: Candle,
    *,
    bar_index: int,
    filled_take_ids: Collection[str],
    final_level: Decimal | None,
) -> tuple[PositionReduction, ...]:
    """Touched, unfilled legs nearest to the anchor first.

    - A leg is touched when the bar reached its level (`high >= level`
      long, `low <= level` short) and fills at exactly that level, even
      when the bar opened beyond it (one continuous-market level-fill
      model, design D8).
    - `final_level` is the touched final take's level, or `None` when
      the final take is not touched or is disabled. Legs strictly beyond
      it are dropped: the final take closes everything first. A leg at
      the same level is kept and comes before the final take.
    - Equal leg levels keep wire order (stable sort).
    """

    if bar_index <= position.entry_fill.bar_index:
        return ()
    long = position.side == "long"
    touched: list[ResolvedPartialTake] = []
    for leg in position.initial_protection.partial_takes:
        if leg.take_id in filled_take_ids:
            continue
        if not (candle.high >= leg.level if long else candle.low <= leg.level):
            continue
        if final_level is not None and (leg.level > final_level if long else leg.level < final_level):
            continue
        touched.append(leg)
    touched.sort(key=lambda leg: leg.level if long else -leg.level)
    return tuple(
        PositionReduction(
            fill_id=f"reduce:{position.position_id}:{leg.take_id}",
            position_id=position.position_id,
            instance_id=position.instance_id,
            side=position.side,
            take_id=leg.take_id,
            bar_index=bar_index,
            time_ms=candle.open_time_ms,
            level=leg.level,
            fill_price=leg.level,
            quantity=leg.quantity,
            fraction_of_initial=leg.fraction_of_initial,
            attribution=leg.attribution,
        )
        for leg in touched
    )
