"""Materialize a backtest outcome from an already-acquired
`HistoricalExecutionProjectionDTO` (I7, `compact-strategy-evaluation-
boundary-v1`) -- the canonical path both `RunSingleInstanceBacktest` and
`RunBatchExperiment` use since I8 (the batch-only legacy
`MaterializeBacktestOutcome` was deleted; there is no separate batch
execution path)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from decimal import Decimal

from research_service.accounting.contracts import TradeAccountingResult, TradeRecord
from research_service.accounting.service import (
    account_closed_execution,
    build_trade_accounting_result,
)
from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.domain.contracts import (
    HistoricalExecutionProjectionDTO,
    HistoricalExecutionProjectionIndex,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketFrame,
    validate_projection_alignment,
)
from research_service.domain.execution import (
    EntryDecision,
    ExecutionLoopResult,
    PositionExecution,
    PositionState,
)
from research_service.execution.managed_policy_events import (
    ManagedPolicyEvent,
    capture_managed_policy_events,
)
from research_service.execution.projection_loop import (
    ManagedReplayProvider,
    run_projection_execution_loop,
)
from research_service.execution.sizing import calculate_full_equity_quantity
from research_service.ports.strategy_engine import StrategyEnginePort


def _generate_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


@dataclass(frozen=True, slots=True)
class SingleInstanceRunOutcome:
    """Authoritative output of one single-instance run materialized against
    the `HistoricalExecutionProjection` (`.v2`) path."""

    run_id: str
    instance_id: str
    strategy_evaluation: HistoricalExecutionProjectionDTO
    execution: ExecutionLoopResult
    accounting: TradeAccountingResult
    managed_policy_events: tuple[ManagedPolicyEvent, ...]


class MaterializeBacktestProjectionOutcome:
    """Continue an already-acquired `HistoricalExecutionProjectionDTO` to a
    materialized Research backtest outcome -- no further Engine range
    evaluation or MDS window resolution."""

    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
        instance_id: str,
        projection: HistoricalExecutionProjectionDTO,
        market_frame: MarketFrame,
    ) -> SingleInstanceRunOutcome:
        validate_projection_alignment(
            projection,
            expected_market=market_frame.market,
            expected_market_data_hash=market_frame.market_data_hash or "",
            expected_bar_count=len(market_frame.candles),
        )
        index = HistoricalExecutionProjectionIndex.build(projection)

        managed_policy_events: list[ManagedPolicyEvent] = []
        managed_provider = (
            self._managed_provider(request, market_frame, managed_policy_events)
            if request.managed_policy_enabled
            else None
        )
        current_equity = request.accounting.initial_equity
        trade_records: list[TradeRecord] = []

        def size_entry(_decision: EntryDecision, actual_fill_price: Decimal) -> Decimal:
            return calculate_full_equity_quantity(
                current_equity,
                actual_fill_price,
                request.accounting.entry_fee_rate,
            )

        def account_close(position_execution: PositionExecution) -> None:
            nonlocal current_equity
            record = account_closed_execution(
                position_execution,
                market_frame,
                request.accounting,
                equity_before=current_equity,
                ordinal=len(trade_records) + 1,
            )
            trade_records.append(record)
            current_equity = record.equity_after

        execution = run_projection_execution_loop(
            instance_id,
            index,
            market_frame,
            request.execution,
            managed_replay_provider=managed_provider,
            entry_quantity_provider=size_entry,
            closed_position_consumer=account_close,
        )
        accounting = build_trade_accounting_result(
            execution,
            request.accounting,
            tuple(trade_records),
        )

        return SingleInstanceRunOutcome(
            run_id=_generate_run_id(),
            instance_id=instance_id,
            strategy_evaluation=projection,
            execution=execution,
            accounting=accounting,
            managed_policy_events=tuple(managed_policy_events),
        )

    def _managed_provider(
        self,
        request: SingleInstanceBacktestRequest,
        market_frame: MarketFrame,
        managed_policy_events: list[ManagedPolicyEvent],
    ) -> ManagedReplayProvider:
        def evaluate(position: PositionState) -> ManagedReplayResult:
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
            managed_policy_events.extend(
                capture_managed_policy_events(
                    replay,
                    position_id=position.position_id,
                    side=position.side,
                )
            )
            return replay

        return evaluate
