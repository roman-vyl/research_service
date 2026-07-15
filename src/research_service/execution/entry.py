"""Deterministic entry execution for the new Research simulator."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from research_service.domain.contracts import MarketFrame, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    EntryDecision,
    EntryFill,
    ExecutionPolicy,
    PositionState,
)
from research_service.execution.protection import (
    protection_ready_at,
    resolve_initial_protection,
)


def _entry_series(
    evaluation: StrategyEvaluationResult,
    side: str,
) -> Sequence[bool]:
    values = evaluation.entries.get(side)
    if not isinstance(values, (list, tuple)):
        raise InvalidRequest(f"Strategy evaluation must contain {side} entries")
    if len(values) != evaluation.bar_count or not all(isinstance(v, bool) for v in values):
        raise InvalidRequest(f"Strategy evaluation {side} entries are invalid")
    return values


def entry_decision_at(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
    *,
    bar_index: int,
) -> EntryDecision | None:
    """Return the legacy-compatible executable entry decision for one bar.

    Legacy BBB used ``entries & stop_ready`` for each side. Long is evaluated
    first and short only when a ready long entry is absent.
    """

    if evaluation.market != market_frame.market:
        raise InvalidRequest("Strategy evaluation and market frame differ")
    if bar_index < 0 or bar_index >= len(market_frame.candles):
        raise InvalidRequest("bar_index is outside the market frame")

    long_entries = _entry_series(evaluation, "long")
    short_entries = _entry_series(evaluation, "short")

    side: str | None = None
    if long_entries[bar_index] and protection_ready_at(
        evaluation, side="long", bar_index=bar_index
    ):
        side = "long"
    elif short_entries[bar_index] and protection_ready_at(
        evaluation, side="short", bar_index=bar_index
    ):
        side = "short"
    if side is None:
        return None

    candle = market_frame.candles[bar_index]
    return EntryDecision(
        instance_id=evaluation.instance_id,
        side=side,
        bar_index=bar_index,
        time_ms=candle.open_time_ms,
        reference_price=candle.close,
    )


def execute_entry(
    decision: EntryDecision,
    policy: ExecutionPolicy,
) -> EntryFill:
    """Execute a signal-bar-close entry with side-aware adverse slippage."""

    one = Decimal("1")
    if decision.side == "long":
        fill_price = decision.reference_price * (one + policy.entry_slippage_rate)
    else:
        fill_price = decision.reference_price * (one - policy.entry_slippage_rate)

    return EntryFill(
        fill_id=f"entry:{decision.instance_id}:{decision.side}:{decision.bar_index}",
        instance_id=decision.instance_id,
        side=decision.side,
        bar_index=decision.bar_index,
        time_ms=decision.time_ms,
        reference_price=decision.reference_price,
        fill_price=fill_price,
        quantity=policy.quantity,
        slippage_rate=policy.entry_slippage_rate,
    )


def try_open_position(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
    policy: ExecutionPolicy,
    *,
    bar_index: int,
    current_position: PositionState | None,
) -> PositionState | None:
    """Open at most one ready, initially protected position for an instance."""

    if current_position is not None:
        if current_position.instance_id != evaluation.instance_id:
            raise InvalidRequest("current position belongs to another instance")
        return current_position

    decision = entry_decision_at(evaluation, market_frame, bar_index=bar_index)
    if decision is None:
        return None
    fill = execute_entry(decision, policy)
    protection = resolve_initial_protection(evaluation, fill)
    return PositionState(
        position_id=f"position:{evaluation.instance_id}:{decision.side}:{bar_index}",
        instance_id=evaluation.instance_id,
        side=decision.side,
        entry_fill=fill,
        initial_protection=protection,
    )
