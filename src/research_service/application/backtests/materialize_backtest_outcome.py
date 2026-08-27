"""Materialize a Research backtest outcome from an already-acquired Strategy
Engine evaluation.

This is the Phase-B continuation seam (`canonical-strategy-instance-v1`
Step 2): given a canonical request, a `StrategyEvaluationResult`, and a
`MarketFrame` already in hand — regardless of whether that evaluation came
from a single `/range` call or (a future) shared `/range-batch` call — it
runs execution/managed-replay/accounting and returns an immutable
`SingleInstanceBacktestOutcome`, without ever calling Strategy Engine's
range evaluation or Market Data Service window resolution itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from research_service.accounting.service import account_execution_loop
from research_service.application.backtests.contracts import (
    SingleInstanceBacktestRequest,
    SingleInstanceBacktestResult,
)
from research_service.application.backtests.strategy_contract import (
    accept_strategy_execution_contract,
)
from research_service.domain.contracts import (
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketFrame,
    StrategyEvaluationResult,
)
from research_service.domain.execution import PositionState
from research_service.execution.loop import ManagedReplayProvider, run_unified_execution_loop
from research_service.execution.managed_policy_events import (
    ManagedPolicyEvent,
    capture_managed_policy_events,
)
from research_service.ports.strategy_engine import StrategyEnginePort


def _generate_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


@dataclass(frozen=True, slots=True)
class SingleInstanceBacktestOutcome:
    """Authoritative output of one backtest execution.

    `result` is the existing persisted/HTTP-facing contract, unchanged.
    `managed_policy_events` is captured evidence sitting alongside it — every
    caller of `RunSingleInstanceBacktest.execute()` (or, directly,
    `MaterializeBacktestOutcome.execute()`) gets both from the same
    authoritative application path, so no caller can silently drop it.
    """

    result: SingleInstanceBacktestResult
    managed_policy_events: tuple[ManagedPolicyEvent, ...]


class MaterializeBacktestOutcome:
    """Continue an already-acquired Strategy Engine evaluation to a
    materialized Research backtest outcome (execution, managed replay,
    accounting, result construction) — no further Engine range evaluation
    or MDS window resolution."""

    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
        evaluation: StrategyEvaluationResult,
        market_frame: MarketFrame,
    ) -> SingleInstanceBacktestOutcome:
        acceptance = accept_strategy_execution_contract(evaluation, market_frame)

        # Owned by this call, not the caller — every entrypoint (standalone
        # POST /backtests, RunBatchExperiment) gets managed-policy events as
        # part of the one authoritative outcome, never as an optional extra
        # a caller has to remember to wire up.
        managed_policy_events: list[ManagedPolicyEvent] = []
        managed_provider = (
            self._managed_provider(
                request,
                market_frame,
                managed_policy_events,
            )
            if request.managed_policy_enabled
            else None
        )
        execution = run_unified_execution_loop(
            evaluation,
            market_frame,
            request.execution,
            managed_replay_provider=managed_provider,
        )
        accounting = account_execution_loop(execution, market_frame, request.accounting)

        # Run identity is generated only here, once acceptance/execution/
        # accounting have all succeeded — a candidate that fails before this
        # point never gets a run_id (research-batch-experiments-v1, "Run
        # identity generated only on success"; canonical-strategy-instance-v1,
        # "Each accepted request creates a new immutable run").
        run_id = _generate_run_id()
        result = SingleInstanceBacktestResult(
            run_id=run_id,
            instance_id=evaluation.instance_id,
            strategy_evaluation=evaluation,
            contract_acceptance=acceptance,
            execution=execution,
            accounting=accounting,
        )
        return SingleInstanceBacktestOutcome(
            result=result,
            managed_policy_events=tuple(managed_policy_events),
        )

    def _managed_provider(
        self,
        request: SingleInstanceBacktestRequest,
        market_frame: MarketFrame,
        managed_policy_events: list[ManagedPolicyEvent],
    ) -> ManagedReplayProvider:
        def evaluate(position: PositionState) -> ManagedReplayResult:
            # BBB v1 managed policy was anchored to the signal-bar close. The
            # entry fill may include Research-owned slippage, so pass the
            # reference price rather than the adjusted fill price.
            #
            # `market_frame.market` (not the originally requested range) so
            # managed replay uses the same effective range as range
            # evaluation and historical candle acquisition — under
            # `full_available` those differ from the originally requested
            # range.
            replay = self._strategy_engine.evaluate_managed_replay(
                ManagedReplayRequest(
                    strategy_id=request.strategy.strategy_id,
                    strategy_spec=request.strategy.raw_spec,
                    market=market_frame.market,
                    trade_id=position.position_id,
                    side=position.side,
                    entry_time_ms=position.entry_fill.time_ms,
                    entry_price=position.entry_fill.reference_price,
                )
            )
            # Capture here, before the loop's ManagedPolicyTimeline (built from
            # this same `replay`) is discarded on position close — this is the
            # one point in the call chain where the Engine's raw events are
            # still attributable to a position.
            managed_policy_events.extend(
                capture_managed_policy_events(
                    replay,
                    position_id=position.position_id,
                    side=position.side,
                )
            )
            return replay

        return evaluate
