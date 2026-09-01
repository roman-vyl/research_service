"""Projection-driven entry execution (I4,
`compact-strategy-evaluation-boundary-v1`).

Consumes `HistoricalExecutionProjectionIndex` (I3) instead of the legacy
dense `StrategyEvaluationResult.entries`/`exit_policy` dict. Additive,
parallel to `execution/entry.py` -- not wired into production
orchestration (route cutover is I7); `run_projection_execution_loop`
(`execution/projection_loop.py`) is the only caller today, and that is
itself only reachable from tests/fixtures until I7.

Reuses `execute_entry`'s existing fill-price formula unchanged
(imported, not reimplemented) -- I4 replaces the *source of strategy
facts* (opportunity lookup instead of dense-array indexing), not the
fill engine.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from research_service.domain.contracts import (
    Candle,
    ExecutableEntryOpportunityDTO,
    HistoricalExecutionProjectionIndex,
    InitialProtectionLegDTO,
    MarketFrame,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    EntryDecision,
    EntryFill,
    ExecutionPolicy,
    InitialProtection,
    InitialProtectionAttribution,
    PositionState,
)
from research_service.execution.entry import execute_entry, resolve_entry_fill_price

EntryQuantityProvider = Callable[[EntryDecision, Decimal], Decimal]


def entry_opportunity_at(
    index: HistoricalExecutionProjectionIndex,
    *,
    bar_index: int,
) -> tuple[str, ExecutableEntryOpportunityDTO] | None:
    """Return the `(side, opportunity)` executable on this bar, or `None`.

    `HistoricalExecutionProjectionDTO` already fails closed on a
    simultaneous long+short opportunity at construction time (I3
    corrective pass), so at most one side can have an opportunity here
    -- long is checked first purely for a deterministic, legacy-
    matching lookup order, not to break a tie that cannot occur.

    Deliberately does NOT reconstruct `entry_allowed`/`stop_ready` from
    separate fields -- `entry_opportunities` in the v2 boundary already
    IS the collapsed `entry_allowed AND protection_ready` fact; absence
    of an opportunity at this bar means absence of a strategy entry,
    full stop.
    """

    long_opportunity = index.lookup_entry(bar_index, "long")
    if long_opportunity is not None:
        return "long", long_opportunity
    short_opportunity = index.lookup_entry(bar_index, "short")
    if short_opportunity is not None:
        return "short", short_opportunity
    return None


def _attribution(
    leg: InitialProtectionLegDTO | None,
) -> InitialProtectionAttribution | None:
    if leg is None:
        return None
    return InitialProtectionAttribution(
        rule_id=leg.attribution.rule_id,
        component_id=leg.attribution.component_id,
        exit_kind=leg.attribution.exit_kind,
    )


def resolve_initial_protection_from_opportunity(
    opportunity: ExecutableEntryOpportunityDTO,
    entry_fill: EntryFill,
) -> InitialProtection:
    """Resolve one opportunity's `initial_stop`/`initial_take` ratios
    (Engine facts) into absolute Research-owned prices (Research facts)
    -- exactly once, at fill time, using the real fill's reference
    price as anchor. Mirrors `execution/protection.py::resolve_initial_
    protection`'s anchor/formula exactly (same `entry_fill.reference_
    price` anchor, same `anchor * (1 ± ratio)` math) -- I4 changes
    where the ratio comes from (an `ExecutableEntryOpportunityDTO` leg
    instead of a dense per-bar series lookup), not the price formula
    itself. Engine's ratio is not an executed price; Research remains
    the sole owner of fill/price semantics.

    Each leg's price and attribution are independently nullable,
    together -- a leg with no applicable rule stays `None`, never a
    fabricated level (`strategy-research-execution-contract-v1`)."""

    if opportunity.side != entry_fill.side:
        raise InvalidRequest("entry opportunity side differs from entry fill side")
    if opportunity.bar_index != entry_fill.bar_index:
        raise InvalidRequest("entry opportunity bar differs from entry fill bar")

    anchor = entry_fill.reference_price
    one = Decimal("1")
    sl_ratio = None if opportunity.initial_stop is None else Decimal(str(opportunity.initial_stop.ratio))
    tp_ratio = None if opportunity.initial_take is None else Decimal(str(opportunity.initial_take.ratio))

    if entry_fill.side == "long":
        stop_price = anchor * (one - sl_ratio) if sl_ratio is not None else None
        take_price = anchor * (one + tp_ratio) if tp_ratio is not None else None
    else:
        stop_price = anchor * (one + sl_ratio) if sl_ratio is not None else None
        take_price = anchor * (one - tp_ratio) if tp_ratio is not None else None

    if stop_price is not None and stop_price <= 0:
        raise InvalidRequest("stop-loss ratio produces a non-positive price")
    if take_price is not None and take_price <= 0:
        raise InvalidRequest("take-profit ratio produces a non-positive price")

    return InitialProtection(
        side=entry_fill.side,
        source_bar_index=entry_fill.bar_index,
        source_time_ms=entry_fill.time_ms,
        anchor_price=anchor,
        stop_loss_ratio=sl_ratio,
        take_profit_ratio=tp_ratio,
        stop_loss_price=stop_price,
        take_profit_price=take_price,
        stop_loss_attribution=_attribution(opportunity.initial_stop),
        take_profit_attribution=_attribution(opportunity.initial_take),
    )


def try_open_projection_position(
    index: HistoricalExecutionProjectionIndex,
    market_frame: MarketFrame,
    policy: ExecutionPolicy,
    *,
    instance_id: str,
    bar_index: int,
    current_position: PositionState | None,
    entry_quantity_provider: EntryQuantityProvider,
) -> PositionState | None:
    """Open at most one ready, initially protected, locked-profile
    position for an instance -- the projection-driven counterpart to
    `execution/entry.py::try_open_position`."""

    if current_position is not None:
        if current_position.instance_id != instance_id:
            raise InvalidRequest("current position belongs to another instance")
        return current_position

    found = entry_opportunity_at(index, bar_index=bar_index)
    if found is None:
        return None
    side, opportunity = found

    candle: Candle = market_frame.candles[bar_index]
    decision = EntryDecision(
        instance_id=instance_id,
        side=side,  # type: ignore[arg-type]
        bar_index=bar_index,
        time_ms=candle.open_time_ms,
        reference_price=candle.close,
    )
    fill_price = resolve_entry_fill_price(decision, policy)
    quantity = entry_quantity_provider(decision, fill_price)
    fill = execute_entry(decision, policy, quantity=quantity)
    protection = resolve_initial_protection_from_opportunity(opportunity, fill)
    return PositionState(
        position_id=f"position:{instance_id}:{side}:{bar_index}",
        instance_id=instance_id,
        side=side,  # type: ignore[arg-type]
        entry_fill=fill,
        initial_protection=protection,
        locked_exit_profile=opportunity.locked_exit_profile,  # type: ignore[arg-type]
    )
