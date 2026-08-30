"""Batch experiment orchestration: one shared Strategy Engine market-frame
acquisition, N candidates streamed and materialized one at a time (I8,
`compact-strategy-evaluation-boundary-v1`).

Three failure levels (research-batch-experiments-v1):

- whole-experiment failures (shared window resolution, the Engine
  `/range-batch` call's shared acquisition/validation, shared historical
  read) propagate out of `execute()` uncaught -- no candidate is
  evaluated, nothing is persisted;
- a per-variant Engine evaluation error (now surfaced inline in the
  stream) isolates one candidate as failed, no materialization
  attempted;
- a per-candidate materialization/persistence failure isolates one
  candidate as failed without disturbing already-persisted siblings.

I8 collapses the old separate "per-variant Engine error inside one
buffered response" level into the same per-candidate try/isolate
boundary as materialize/persist failures, since Engine acquisition is no
longer a separate response field to inspect before this loop starts --
see `research-batch-lifecycle-v1`.
"""

from __future__ import annotations

from research_service.application.backtests.from_deployable_instance import (
    build_backtest_request,
)
from research_service.application.backtests.history_window import ResolveBacktestWindow
from research_service.application.backtests.materialize_backtest_projection import (
    MaterializeBacktestProjectionOutcome,
)
from research_service.application.backtests.persist_run import PersistSingleInstanceRun
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
    HistoricalExecutionProjectionDTO,
    MarketFrame,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariant,
    StrategyEvaluationBatchVariantOutcome,
)
from research_service.domain.strategy_instance import derive_strategy_instance_id
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import StrategyEnginePort


class RunBatchExperiment:
    """Resolve one shared market window, stream every candidate's
    `HistoricalExecutionProjection` through one Strategy Engine
    `/range-batch` call, then materialize/persist each successful
    candidate independently via `MaterializeBacktestProjectionOutcome`/
    `PersistSingleInstanceRun` — the same canonical, single-instance-
    production path, never a separate batch execution/accounting path —
    releasing each candidate's state before the next is evaluated."""

    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        market_data: MarketDataPort,
        materialize: MaterializeBacktestProjectionOutcome,
        persist_run: PersistSingleInstanceRun,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._market_data = market_data
        self._window_planner = ResolveBacktestWindow(market_data)
        self._materialize = materialize
        self._persist_run = persist_run

    def execute(self, request: BatchExperimentRequest) -> BatchExperimentResult:
        # --- shared Phase A: one window, one shared MarketFrame ----------
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
        # This call itself sends no request and returns immediately --
        # `evaluate_range_batch` is a generator function, so nothing here
        # executes until `outcomes` is iterated below. The real HTTP
        # request, and Engine's shared acquisition/validation, happen on
        # the first iteration step (inside the dict comprehension further
        # down); a terminal acquisition failure surfaces there, before
        # any candidate is settled, so no candidate is ever persisted in
        # that case (research-batch-lifecycle-v1) -- but this is not the
        # same as the failure happening before this method returns.
        outcomes = self._strategy_engine.evaluate_range_batch(batch_request)
        market_frame = self._market_data.read_historical_range(
            window.market,
            expected_market_data_hash=window.market_data_hash,
        )

        candidates_by_id = {candidate.candidate_id: candidate for candidate in request.candidates}

        # --- per-candidate Phase B: streamed, one heavy outcome resident
        # at a time -- each `_settle_candidate` call materializes,
        # persists, and releases its `HistoricalExecutionProjectionDTO`/
        # execution/accounting state before the next `outcome` is even
        # produced by the (lazy) generator. Only the small `BatchCandidate
        # Result` summaries are collected, keyed by candidate_id so the
        # final list can be restored to request order regardless of the
        # order outcomes actually streamed in (`research-batch-
        # experiments-v1`: "Sequential execution order"/"Batch summary...
        # lists candidates in request order").
        results_by_id = {
            outcome.variant_id: self._settle_candidate(
                request,
                candidates_by_id[outcome.variant_id],
                instance_ids[outcome.variant_id],
                outcome,
                market_frame,
            )
            for outcome in outcomes
        }
        results = tuple(results_by_id[candidate.candidate_id] for candidate in request.candidates)

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
        instance_id: str,
        outcome: StrategyEvaluationBatchVariantOutcome,
        market_frame: MarketFrame,
    ) -> BatchCandidateResult:
        if outcome.result is None:
            # Per-variant Engine evaluation failure. No projection exists,
            # so no materialization is attempted.
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=None,
                instance_id=instance_id,
                status="failed",
                error_type="StrategyEngineVariantError",
                error_message=str(outcome.error),
                metadata=candidate.metadata,
            )

        projection: HistoricalExecutionProjectionDTO = outcome.result
        backtest_request = build_backtest_request(
            candidate.strategy,
            range_policy=request.range_policy,
            range=request.range,
            execution=candidate.execution,
            accounting=candidate.accounting,
            managed_policy_enabled=candidate.managed_policy_enabled,
        )
        try:
            materialized = self._materialize.execute(
                backtest_request, instance_id, projection, market_frame
            )
            persisted = self._persist_run.execute(
                backtest_request,
                run_id=materialized.run_id,
                instance_id=materialized.instance_id,
                strategy_evaluation=materialized.strategy_evaluation,
                execution=materialized.execution,
                accounting=materialized.accounting,
                managed_policy_events=materialized.managed_policy_events,
            )
        except Exception as exc:  # noqa: BLE001 -- failure isolation is the batch contract
            # dataclass-based ResearchServiceError subclasses (e.g.
            # UpstreamServiceError) don't populate BaseException.args
            # unless constructed with a positional first arg, so str(exc)
            # is unreliable for them -- prefer the dataclass's own
            # `.message` field when present.
            message = getattr(exc, "message", None) or str(exc)
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=None,
                instance_id=instance_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=message,
                metadata=candidate.metadata,
            )

        accounting = materialized.accounting
        summary = derive_batch_candidate_summary(accounting)
        return BatchCandidateResult(
            candidate_id=candidate.candidate_id,
            run_id=materialized.run_id,
            instance_id=materialized.instance_id,
            status="completed",
            artifact_path=persisted.artifact_path,
            realised_trade_count=accounting.realised_trade_count,
            open_position_count=accounting.open_position_count,
            final_equity=accounting.final_equity,
            gross_pnl=accounting.gross_pnl,
            fees_paid=accounting.fees_paid,
            net_pnl=accounting.net_pnl,
            market_data_hash=materialized.strategy_evaluation.market_data_hash,
            return_pct=summary.return_pct,
            win_rate=summary.win_rate,
            profit_factor=summary.profit_factor,
            max_drawdown=summary.max_drawdown,
            long=summary.long,
            short=summary.short,
            metadata=candidate.metadata,
        )
