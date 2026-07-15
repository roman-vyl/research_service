"""Unified static and managed exit arbitration for one executable bar."""

from __future__ import annotations

from typing import Sequence

from research_service.domain.contracts import Candle, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    ExitArbitrationResult,
    ExitCandidate,
    ExitFill,
    PositionState,
)
from research_service.execution.managed_policy import (
    ManagedEffectiveState,
    collect_managed_exit_candidates,
)
from research_service.execution.static_exits import collect_static_exit_candidates

_CANDIDATE_PRIORITY: dict[str, int] = {
    "stop_loss": 1,
    "managed_stop": 2,
    "take_profit": 3,
    "runtime_protective": 4,
    "runtime_take": 5,
    "runtime_close": 6,
    "runtime_exit": 6,
    "signal": 7,
}


def collect_unified_exit_candidates(
    evaluation: StrategyEvaluationResult,
    position: PositionState,
    candle: Candle,
    managed_state: ManagedEffectiveState | None,
    *,
    bar_index: int,
) -> tuple[ExitCandidate, ...]:
    """Collect all Research-owned executable candidates for one bar.

    Strategy Engine owns the policy state. Research Service applies that state
    to OHLC and preserves the legacy rule that ``disable_initial_tp`` suppresses
    only the initial fixed take-profit candidate.
    """

    active_take_profile = (
        managed_state.active_take_profile if managed_state is not None else "initial"
    )
    static_candidates = collect_static_exit_candidates(
        evaluation,
        position,
        candle,
        bar_index=bar_index,
        active_take_profile=active_take_profile,
    )
    managed_candidates = collect_managed_exit_candidates(
        position,
        candle,
        managed_state,
        bar_index=bar_index,
    )
    return (*static_candidates, *managed_candidates)


def arbitrate_unified_exit_candidates(
    candidates: Sequence[ExitCandidate],
) -> ExitArbitrationResult:
    """Apply the exact BBB v1 priority across both exit layers."""

    if not candidates:
        return ExitArbitrationResult(winner=None, losing_candidates=())

    bar_indices = {candidate.bar_index for candidate in candidates}
    times = {candidate.time_ms for candidate in candidates}
    if len(bar_indices) != 1 or len(times) != 1:
        raise InvalidRequest("exit candidates from different bars cannot be arbitrated together")

    ordered = sorted(
        candidates,
        key=lambda candidate: (
            _CANDIDATE_PRIORITY.get(candidate.candidate_type, 99),
            candidate.reason,
        ),
    )
    return ExitArbitrationResult(
        winner=ordered[0],
        losing_candidates=tuple(ordered[1:]),
    )


def execute_unified_exit(
    position: PositionState,
    arbitration: ExitArbitrationResult,
) -> ExitFill | None:
    """Convert the selected candidate into the canonical Research exit fill."""

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
        layer=winner.layer,
        rule_id=winner.rule_id,
        component_id=winner.component_id,
        exit_kind=winner.exit_kind,
    )
