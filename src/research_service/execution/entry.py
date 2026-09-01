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
    ExecutionSide,
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


def validated_entry_series(
    evaluation: StrategyEvaluationResult,
) -> tuple[Sequence[bool], Sequence[bool]]:
    """Validate both sides' `entries` arrays exactly once (`_entry_series`'s
    full-array `isinstance`/length checks are O(bar_count) each) so a
    bar-by-bar caller can validate once per execution run and then do O(1)
    per-bar lookups, instead of repeating this scan on every bar
    (`execution/loop.py::run_unified_execution_loop` was doing exactly
    that -- O(bar_count) work called once per bar, i.e. O(bar_count^2)
    for a full run -- before this fix). Semantics are unchanged: this is
    the same validation `entry_decision_at` already ran per call, just
    hoisted so it runs once instead of once per bar."""

    return _entry_series(evaluation, "long"), _entry_series(evaluation, "short")


def entry_decision_at(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
    *,
    bar_index: int,
    entries: tuple[Sequence[bool], Sequence[bool]] | None = None,
) -> EntryDecision | None:
    """Return the legacy-compatible executable entry decision for one bar.

    Legacy BBB used ``entries & stop_ready`` for each side. Long is evaluated
    first and short only when a ready long entry is absent.

    `entries`: pass the result of `validated_entry_series(evaluation)` when
    calling this once per bar in a loop, to skip re-validating the full
    arrays on every call (see that function's docstring). Defaults to
    `None`, which validates on this call alone -- unchanged behavior for
    any caller that invokes this occasionally rather than in a bar loop.
    """

    if evaluation.market != market_frame.market:
        raise InvalidRequest("Strategy evaluation and market frame differ")
    if bar_index < 0 or bar_index >= len(market_frame.candles):
        raise InvalidRequest("bar_index is outside the market frame")

    if entries is None:
        long_entries, short_entries = validated_entry_series(evaluation)
    else:
        long_entries, short_entries = entries

    side: ExecutionSide | None = None
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
    *,
    quantity: Decimal = Decimal("1"),
) -> EntryFill:
    """Execute a signal-bar-close entry with side-aware adverse slippage."""

    fill_price = resolve_entry_fill_price(decision, policy)

    return EntryFill(
        fill_id=f"entry:{decision.instance_id}:{decision.side}:{decision.bar_index}",
        instance_id=decision.instance_id,
        side=decision.side,
        bar_index=decision.bar_index,
        time_ms=decision.time_ms,
        reference_price=decision.reference_price,
        fill_price=fill_price,
        quantity=quantity,
        slippage_rate=policy.entry_slippage_rate,
    )


def resolve_entry_fill_price(decision: EntryDecision, policy: ExecutionPolicy) -> Decimal:
    """Resolve side-aware adverse entry slippage before position sizing."""

    one = Decimal("1")
    if decision.side == "long":
        return decision.reference_price * (one + policy.entry_slippage_rate)
    return decision.reference_price * (one - policy.entry_slippage_rate)


def try_open_position(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
    policy: ExecutionPolicy,
    *,
    bar_index: int,
    current_position: PositionState | None,
    entries: tuple[Sequence[bool], Sequence[bool]] | None = None,
    quantity: Decimal = Decimal("1"),
) -> PositionState | None:
    """Open at most one ready, initially protected position for an instance.

    `entries`: see `entry_decision_at`'s docstring -- pass
    `validated_entry_series(evaluation)` once per execution run when
    calling this in a bar loop.
    """

    if current_position is not None:
        if current_position.instance_id != evaluation.instance_id:
            raise InvalidRequest("current position belongs to another instance")
        return current_position

    decision = entry_decision_at(evaluation, market_frame, bar_index=bar_index, entries=entries)
    if decision is None:
        return None
    fill = execute_entry(decision, policy, quantity=quantity)
    protection = resolve_initial_protection(evaluation, fill)
    return PositionState(
        position_id=f"position:{evaluation.instance_id}:{decision.side}:{bar_index}",
        instance_id=evaluation.instance_id,
        side=decision.side,
        entry_fill=fill,
        initial_protection=protection,
    )
