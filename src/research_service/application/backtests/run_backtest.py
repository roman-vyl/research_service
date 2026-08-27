"""Authoritative single-instance backtest orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from research_service.accounting.service import account_execution_loop
from research_service.application.backtests.contracts import (
    SingleInstanceBacktestRequest,
    SingleInstanceBacktestResult,
)
from research_service.application.backtests.history_window import ResolveBacktestWindow
from research_service.application.backtests.strategy_contract import (
    accept_strategy_execution_contract,
)
from research_service.domain.contracts import (
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketRange,
)
from research_service.domain.execution import PositionState
from research_service.execution.loop import ManagedReplayProvider, run_unified_execution_loop
from research_service.execution.managed_policy_events import (
    ManagedPolicyEvent,
    capture_managed_policy_events,
)
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import StrategyEnginePort


@dataclass(frozen=True, slots=True)
class SingleInstanceBacktestOutcome:
    """Authoritative output of one backtest execution.

    `result` is the existing persisted/HTTP-facing contract, unchanged.
    `managed_policy_events` is captured evidence sitting alongside it — every
    caller of `RunSingleInstanceBacktest.execute()` gets both from the same
    authoritative application path, so no caller can silently drop it.
    """

    result: SingleInstanceBacktestResult
    managed_policy_events: tuple[ManagedPolicyEvent, ...]


class RunSingleInstanceBacktest:
    """Compose Strategy Engine, MDS, execution and accounting for one instance."""

    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        market_data: MarketDataPort,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._market_data = market_data
        self._window_planner = ResolveBacktestWindow(market_data)

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
    ) -> SingleInstanceBacktestOutcome:
        window = self._window_planner.execute(
            request.strategy.market,
            request.range_policy,
        )
        strategy_request = request.strategy.model_copy(
            update={
                "market": window.market,
                "expected_market_data_hash": window.market_data_hash,
            }
        )
        evaluation = self._strategy_engine.evaluate_range(strategy_request)
        market_frame = self._market_data.read_historical_range(
            window.market,
            expected_market_data_hash=window.market_data_hash,
        )
        acceptance = accept_strategy_execution_contract(evaluation, market_frame)

        # Owned by this call, not the caller — every entrypoint (standalone
        # POST /backtests, RunBatchExperiment) gets managed-policy events as
        # part of the one authoritative outcome, never as an optional extra
        # a caller has to remember to wire up.
        managed_policy_events: list[ManagedPolicyEvent] = []
        managed_provider = (
            self._managed_provider(request, window.market, managed_policy_events)
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

        result = SingleInstanceBacktestResult(
            run_id=request.run_id,
            instance_id=request.strategy.instance_id,
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
        resolved_market: MarketRange,
        managed_policy_events: list[ManagedPolicyEvent],
    ) -> ManagedReplayProvider:
        def evaluate(position: PositionState) -> ManagedReplayResult:
            # BBB v1 managed policy was anchored to the signal-bar close. The
            # entry fill may include Research-owned slippage, so pass the
            # reference price rather than the adjusted fill price.
            #
            # `resolved_market` (not `request.strategy.market`) so managed
            # replay uses the same effective range as range evaluation and
            # historical candle acquisition — under `full_available` those
            # differ from the originally requested range.
            replay = self._strategy_engine.evaluate_managed_replay(
                ManagedReplayRequest(
                    strategy_id=request.strategy.strategy_id,
                    strategy_version=request.strategy.strategy_version,
                    instance_id=request.strategy.instance_id,
                    strategy_spec=request.strategy.strategy_spec,
                    market=resolved_market,
                    trade_id=position.position_id,
                    side=position.side,
                    entry_time_ms=position.entry_fill.time_ms,
                    entry_price=position.entry_fill.reference_price,
                    compatibility_profile=request.strategy.compatibility_profile,
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
