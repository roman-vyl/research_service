"""Unified bar-by-bar execution state machine for one strategy instance."""

from __future__ import annotations

from collections.abc import Callable

from research_service.domain.contracts import (
    ManagedReplayResult,
    MarketFrame,
    StrategyEvaluationResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    ExecutionEvent,
    ExecutionLoopResult,
    ExecutionPolicy,
    ExitArbitrationResult,
    ExitFill,
    PositionExecution,
    PositionState,
)
from research_service.execution.entry import try_open_position, validated_entry_series
from research_service.execution.managed_policy import (
    ManagedPolicyTimeline,
    build_managed_policy_timeline,
)
from research_service.execution.unified_exits import (
    arbitrate_unified_exit_candidates,
    collect_unified_exit_candidates,
    execute_unified_exit,
)

ManagedReplayProvider = Callable[[PositionState], ManagedReplayResult | None]


def run_unified_execution_loop(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
    policy: ExecutionPolicy,
    *,
    managed_replay_provider: ManagedReplayProvider | None = None,
) -> ExecutionLoopResult:
    """Execute one strategy instance across an aligned market range.

    The loop mirrors the legacy ordering:

    1. a position that existed at bar open may exit on that bar;
    2. a bar that began with an open position cannot also open a replacement;
    3. a position opened on the current close cannot exit on the same bar;
    4. managed decisions are consumed only through their next-bar timeline.

    The output contains execution facts only. Fees, PnL, MFE/MAE accounting and
    run artifacts belong to later Research Service stages.
    """

    _validate_execution_grid(evaluation, market_frame)
    # Validated once per run, not once per bar -- see validated_entry_series's
    # docstring for the O(bar_count^2) this avoids.
    entries = validated_entry_series(evaluation)

    current_position: PositionState | None = None
    current_timeline: ManagedPolicyTimeline | None = None
    completed: list[PositionExecution] = []
    events: list[ExecutionEvent] = []

    for bar_index, candle in enumerate(market_frame.candles):
        position_was_open_at_bar_start = current_position is not None

        if current_position is not None:
            managed_state = (
                current_timeline.state_for_time(candle.open_time_ms)
                if current_timeline is not None
                else None
            )
            candidates = collect_unified_exit_candidates(
                evaluation,
                current_position,
                candle,
                managed_state,
                bar_index=bar_index,
            )
            arbitration = arbitrate_unified_exit_candidates(candidates)
            exit_fill = execute_unified_exit(current_position, arbitration)
            if exit_fill is not None:
                completed.append(
                    PositionExecution(
                        position=current_position,
                        status="closed",
                        exit_fill=exit_fill,
                        exit_arbitration=arbitration,
                    )
                )
                events.append(
                    _exit_event(
                        current_position,
                        exit_fill=exit_fill,
                        arbitration=arbitration,
                    )
                )
                current_position = None
                current_timeline = None

        # Legacy invariant: a position present at bar open blocks replacement
        # entry on that same bar, even when it was closed during arbitration.
        if not position_was_open_at_bar_start:
            opened = try_open_position(
                evaluation,
                market_frame,
                policy,
                bar_index=bar_index,
                current_position=current_position,
                entries=entries,
            )
            if opened is not None and opened is not current_position:
                current_position = opened
                current_timeline = _resolve_managed_timeline(
                    opened,
                    managed_replay_provider=managed_replay_provider,
                )
                events.append(_entry_event(opened))

    if current_position is not None:
        completed.append(PositionExecution(position=current_position, status="open"))
        last_candle = market_frame.candles[-1]
        events.append(
            ExecutionEvent(
                event_id=f"open:{current_position.position_id}:{last_candle.open_time_ms}",
                event_type="position_left_open",
                instance_id=current_position.instance_id,
                position_id=current_position.position_id,
                side=current_position.side,
                bar_index=len(market_frame.candles) - 1,
                time_ms=last_candle.open_time_ms,
                metadata={
                    "last_close": str(last_candle.close),
                    "entry_bar_index": current_position.entry_fill.bar_index,
                },
            )
        )

    return ExecutionLoopResult(
        instance_id=evaluation.instance_id,
        market=market_frame.market,
        positions=tuple(completed),
        events=tuple(events),
        final_open_position=current_position,
    )


def _validate_execution_grid(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
) -> None:
    if evaluation.market != market_frame.market:
        raise InvalidRequest("Strategy evaluation and market frame differ")
    if evaluation.bar_count != len(market_frame.candles):
        raise InvalidRequest("Strategy evaluation bar count differs from market frame")
    candle_times = tuple(candle.open_time_ms for candle in market_frame.candles)
    if evaluation.time_ms != candle_times:
        raise InvalidRequest("Strategy evaluation timestamps differ from market frame")


def _resolve_managed_timeline(
    position: PositionState,
    *,
    managed_replay_provider: ManagedReplayProvider | None,
) -> ManagedPolicyTimeline | None:
    if managed_replay_provider is None:
        return None
    replay = managed_replay_provider(position)
    if replay is None:
        return None
    return build_managed_policy_timeline(replay, position)


def _entry_event(position: PositionState) -> ExecutionEvent:
    fill = position.entry_fill
    return ExecutionEvent(
        event_id=f"event:{fill.fill_id}",
        event_type="entry_filled",
        instance_id=position.instance_id,
        position_id=position.position_id,
        side=position.side,
        bar_index=fill.bar_index,
        time_ms=fill.time_ms,
        fill_id=fill.fill_id,
        metadata={
            "reference_price": str(fill.reference_price),
            "fill_price": str(fill.fill_price),
            "quantity": str(fill.quantity),
            "stop_loss_price": _decimal_text(position.initial_protection.stop_loss_price),
            "take_profit_price": _decimal_text(position.initial_protection.take_profit_price),
        },
    )


def _exit_event(
    position: PositionState,
    *,
    exit_fill: ExitFill,
    arbitration: ExitArbitrationResult,
) -> ExecutionEvent:
    winner = arbitration.winner
    assert winner is not None
    return ExecutionEvent(
        event_id=f"event:{exit_fill.fill_id}",
        event_type="exit_filled",
        instance_id=position.instance_id,
        position_id=position.position_id,
        side=position.side,
        bar_index=exit_fill.bar_index,
        time_ms=exit_fill.time_ms,
        fill_id=exit_fill.fill_id,
        metadata={
            "candidate_type": exit_fill.candidate_type,
            "layer": exit_fill.layer,
            "reason": exit_fill.reason,
            "reference_level": str(exit_fill.reference_level),
            "fill_price": str(exit_fill.fill_price),
            "rule_id": exit_fill.rule_id,
            "component_id": exit_fill.component_id,
            "exit_kind": exit_fill.exit_kind,
            "losing_candidate_types": [
                candidate.candidate_type for candidate in arbitration.losing_candidates
            ],
            "winner_reason": winner.reason,
        },
    )


def _decimal_text(value: object) -> str | None:
    return None if value is None else str(value)
