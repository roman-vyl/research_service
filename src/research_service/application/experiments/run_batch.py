"""Batch experiment orchestration: one shared Strategy Engine evaluation,
N candidate materializations.

Three failure levels (research-batch-experiments-v1):

- whole-experiment failures (shared window resolution, the Engine
  `/range-batch` call itself, shared historical read, response
  correlation) propagate out of `execute()` uncaught -- no candidate loop
  starts, nothing is persisted;
- a per-variant Engine error isolates one candidate as failed, no
  materialization attempted;
- a per-candidate materialization/persistence failure isolates one
  candidate as failed without disturbing already-persisted siblings.
"""

from __future__ import annotations

from research_service.application.backtests.artifacts import PersistSingleInstanceBacktest
from research_service.application.backtests.from_deployable_instance import (
    build_backtest_request,
)
from research_service.application.backtests.history_window import ResolveBacktestWindow
from research_service.application.backtests.materialize_backtest_outcome import (
    MaterializeBacktestOutcome,
)
from research_service.application.experiments.candidate_summary import (
    derive_batch_candidate_summary,
)
from research_service.application.experiments.contracts import (
    BatchCandidateRequest,
    BatchCandidateResult,
    BatchExperimentRequest,
    BatchExperimentResult,
)
from research_service.domain.contracts import (
    MarketFrame,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariant,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationResult,
)
from research_service.domain.strategy_instance import derive_strategy_instance_id
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import StrategyEnginePort


class RunBatchExperiment:
    """Resolve one shared market window, evaluate every candidate through
    one Strategy Engine `/range-batch` call, read one shared `MarketFrame`,
    then materialize/persist each successful candidate independently via
    `MaterializeBacktestOutcome` — never `RunSingleInstanceBacktest`, never
    a per-candidate Engine range call."""

    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        market_data: MarketDataPort,
        materialize: MaterializeBacktestOutcome,
        persist_backtest: PersistSingleInstanceBacktest,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._market_data = market_data
        self._window_planner = ResolveBacktestWindow(market_data)
        self._materialize = materialize
        self._persist_backtest = persist_backtest

    def execute(self, request: BatchExperimentRequest) -> BatchExperimentResult:
        # --- shared Phase A: one window, one Engine call, one frame -------
        first_strategy = request.candidates[0].strategy
        window = self._window_planner.execute(
            ticker=first_strategy.ticker,
            timeframe=first_strategy.base_timeframe,
            explicit_range=request.range,
            range_policy=request.range_policy,
        )
        instance_ids = {
            candidate.candidate_id: derive_strategy_instance_id(
                strategy_id=candidate.strategy.strategy_id,
                ticker=candidate.strategy.ticker,
                base_timeframe=candidate.strategy.base_timeframe,
                raw_spec=candidate.strategy.raw_spec,
            )
            for candidate in request.candidates
        }
        batch_request = StrategyEvaluationBatchRequest(
            market=window.market,
            variants=tuple(
                StrategyEvaluationBatchVariant(
                    variant_id=candidate.candidate_id,
                    instance_id=instance_ids[candidate.candidate_id],
                    strategy_id=candidate.strategy.strategy_id,
                    strategy_spec=candidate.strategy.raw_spec,
                )
                for candidate in request.candidates
            ),
            expected_market_data_hash=window.market_data_hash,
        )
        outcomes = self._strategy_engine.evaluate_range_batch(batch_request)
        outcomes_by_candidate = {outcome.variant_id: outcome for outcome in outcomes}
        market_frame = self._market_data.read_historical_range(
            window.market,
            expected_market_data_hash=window.market_data_hash,
        )

        # --- per-candidate Phase B: isolated materialization/persistence --
        results = tuple(
            self._settle_candidate(
                request, candidate, outcomes_by_candidate[candidate.candidate_id], market_frame
            )
            for candidate in request.candidates
        )

        failed_count = sum(item.status == "failed" for item in results)
        return BatchExperimentResult(
            experiment_id=request.experiment_id,
            status="completed" if failed_count == 0 else "completed_with_failures",
            candidate_count=len(results),
            completed_count=len(results) - failed_count,
            failed_count=failed_count,
            candidates=results,
        )

    def _settle_candidate(
        self,
        request: BatchExperimentRequest,
        candidate: BatchCandidateRequest,
        outcome: StrategyEvaluationBatchVariantOutcome,
        market_frame: MarketFrame,
    ) -> BatchCandidateResult:
        if outcome.result is None:
            # Level 2: per-variant Engine failure. No evaluation exists, so
            # no materialization is attempted; instance_id is still a pure
            # function of the candidate's own identity subset.
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=None,
                instance_id=derive_strategy_instance_id(
                    strategy_id=candidate.strategy.strategy_id,
                    ticker=candidate.strategy.ticker,
                    base_timeframe=candidate.strategy.base_timeframe,
                    raw_spec=candidate.strategy.raw_spec,
                ),
                status="failed",
                error_type="StrategyEngineVariantError",
                error_message=str(outcome.error),
                metadata=candidate.metadata,
            )

        evaluation: StrategyEvaluationResult = outcome.result
        backtest_request = build_backtest_request(
            candidate.strategy,
            range_policy=request.range_policy,
            range=request.range,
            execution=candidate.execution,
            accounting=candidate.accounting,
            managed_policy_enabled=candidate.managed_policy_enabled,
        )
        try:
            # Level 3: per-candidate materialization/persistence failure.
            materialized = self._materialize.execute(backtest_request, evaluation, market_frame)
            persisted = self._persist_backtest.execute(
                backtest_request,
                materialized.result,
                materialized.managed_policy_events,
            )
        except Exception as exc:  # noqa: BLE001 -- failure isolation is the batch contract
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=None,
                instance_id=evaluation.instance_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
                metadata=candidate.metadata,
            )

        accounting = materialized.result.accounting
        summary = derive_batch_candidate_summary(accounting)
        return BatchCandidateResult(
            candidate_id=candidate.candidate_id,
            run_id=materialized.result.run_id,
            instance_id=materialized.result.instance_id,
            status="completed",
            artifact_path=persisted.artifact_path,
            realised_trade_count=accounting.realised_trade_count,
            open_position_count=accounting.open_position_count,
            final_equity=accounting.final_equity,
            gross_pnl=accounting.gross_pnl,
            fees_paid=accounting.fees_paid,
            net_pnl=accounting.net_pnl,
            market_data_hash=materialized.result.strategy_evaluation.market_data_hash,
            return_pct=summary.return_pct,
            win_rate=summary.win_rate,
            profit_factor=summary.profit_factor,
            max_drawdown=summary.max_drawdown,
            long=summary.long,
            short=summary.short,
            metadata=candidate.metadata,
        )
