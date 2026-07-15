"""Legacy-compatible static exit candidate collection and arbitration."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from research_service.domain.contracts import Candle, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    ExitArbitrationResult,
    ExitCandidate,
    ExitFill,
    PositionState,
)

_STATIC_PRIORITY = {
    "stop_loss": 1,
    "take_profit": 3,
    "signal": 7,
}


def _signal_series(
    evaluation: StrategyEvaluationResult,
    *,
    side: str,
) -> Sequence[object]:
    raw = evaluation.exit_policy.get("signal_exit")
    if not isinstance(raw, Mapping):
        raise InvalidRequest("Strategy evaluation exit_policy.signal_exit must be an object")
    values = raw.get(side)
    if not isinstance(values, (list, tuple)):
        raise InvalidRequest(f"Strategy evaluation signal_exit.{side} must be a series")
    if len(values) != evaluation.bar_count:
        raise InvalidRequest(
            f"Strategy evaluation signal_exit.{side} length differs from market grid"
        )
    return values


def _distance_fill_price(
    side: str,
    candle: Candle,
    *,
    level: Decimal,
    is_loss: bool,
) -> Decimal | None:
    """Mirror BBB/vectorbt gap and intrabar distance-exit semantics."""

    if side == "long":
        if is_loss:
            if candle.open <= level:
                return candle.open
            if candle.low <= level <= candle.high:
                return level
        else:
            if level <= candle.open:
                return candle.open
            if candle.low <= level <= candle.high:
                return level
    else:
        if is_loss:
            if level <= candle.open:
                return candle.open
            if candle.low <= level <= candle.high:
                return level
        else:
            if candle.open <= level:
                return candle.open
            if candle.low <= level <= candle.high:
                return level
    return None


def collect_static_exit_candidates(
    evaluation: StrategyEvaluationResult,
    position: PositionState,
    candle: Candle,
    *,
    bar_index: int,
    active_take_profile: str = "initial",
) -> tuple[ExitCandidate, ...]:
    """Collect SL, TP and signal candidates for a position open at bar start."""

    if position.instance_id != evaluation.instance_id:
        raise InvalidRequest("position belongs to another strategy instance")
    if bar_index < 0 or bar_index >= evaluation.bar_count:
        raise InvalidRequest("bar_index is outside the strategy evaluation")
    if candle.open_time_ms != evaluation.time_ms[bar_index]:
        raise InvalidRequest("candle timestamp differs from strategy evaluation")
    if bar_index <= position.entry_fill.bar_index:
        return ()

    protection = position.initial_protection
    candidates: list[ExitCandidate] = []

    if protection.stop_loss_price is not None:
        price = _distance_fill_price(
            position.side,
            candle,
            level=protection.stop_loss_price,
            is_loss=True,
        )
        if price is not None:
            candidates.append(
                ExitCandidate(
                    candidate_type="stop_loss",
                    layer="exit_policy",
                    bar_index=bar_index,
                    time_ms=candle.open_time_ms,
                    reference_level=protection.stop_loss_price,
                    fill_price=price,
                    reason="stop_loss",
                )
            )

    if active_take_profile != "disable_initial_tp" and protection.take_profit_price is not None:
        price = _distance_fill_price(
            position.side,
            candle,
            level=protection.take_profit_price,
            is_loss=False,
        )
        if price is not None:
            candidates.append(
                ExitCandidate(
                    candidate_type="take_profit",
                    layer="exit_policy",
                    bar_index=bar_index,
                    time_ms=candle.open_time_ms,
                    reference_level=protection.take_profit_price,
                    fill_price=price,
                    reason="take_profit",
                )
            )

    signal = _signal_series(evaluation, side=position.side)[bar_index]
    if not isinstance(signal, bool):
        raise InvalidRequest("signal_exit values must be booleans")
    if signal:
        candidates.append(
            ExitCandidate(
                candidate_type="signal",
                layer="exit_policy",
                bar_index=bar_index,
                time_ms=candle.open_time_ms,
                reference_level=candle.close,
                fill_price=candle.close,
                reason="signal",
            )
        )

    return tuple(candidates)


def arbitrate_static_exit_candidates(
    candidates: Sequence[ExitCandidate],
) -> ExitArbitrationResult:
    """Apply BBB same-bar priority: stop loss, take profit, then signal."""

    if not candidates:
        return ExitArbitrationResult(winner=None, losing_candidates=())
    bar_indices = {candidate.bar_index for candidate in candidates}
    if len(bar_indices) != 1:
        raise InvalidRequest("exit candidates from different bars cannot be arbitrated together")
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            _STATIC_PRIORITY.get(candidate.candidate_type, 99),
            candidate.reason,
        ),
    )
    return ExitArbitrationResult(
        winner=ordered[0],
        losing_candidates=tuple(ordered[1:]),
    )


def execute_static_exit(
    position: PositionState,
    arbitration: ExitArbitrationResult,
) -> ExitFill | None:
    winner = arbitration.winner
    if winner is None:
        return None
    return ExitFill(
        fill_id=f"exit:{position.position_id}:{winner.candidate_type}:{winner.bar_index}",
        position_id=position.position_id,
        instance_id=position.instance_id,
        side=position.side,
        candidate_type=winner.candidate_type,
        bar_index=winner.bar_index,
        time_ms=winner.time_ms,
        reference_level=winner.reference_level,
        fill_price=winner.fill_price,
        reason=winner.reason,
    )
