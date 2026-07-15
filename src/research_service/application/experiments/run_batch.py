"""Sequential batch orchestration over the single-instance backtest use case."""

from __future__ import annotations

from research_service.application.backtests.artifacts import PersistSingleInstanceBacktest
from research_service.application.backtests.run_backtest import RunSingleInstanceBacktest
from research_service.application.experiments.contracts import (
    BatchCandidateRequest,
    BatchCandidateResult,
    BatchExperimentRequest,
    BatchExperimentResult,
)


class RunBatchExperiment:
    """Run candidates sequentially with per-candidate failure isolation."""

    def __init__(
        self,
        run_backtest: RunSingleInstanceBacktest,
        persist_backtest: PersistSingleInstanceBacktest,
    ) -> None:
        self._run_backtest = run_backtest
        self._persist_backtest = persist_backtest

    def execute(self, request: BatchExperimentRequest) -> BatchExperimentResult:
        results: list[BatchCandidateResult] = []
        for candidate in request.candidates:
            results.append(self._run_candidate(candidate))

        failed_count = sum(item.status == "failed" for item in results)
        return BatchExperimentResult(
            experiment_id=request.experiment_id,
            status="completed" if failed_count == 0 else "completed_with_failures",
            candidate_count=len(results),
            completed_count=len(results) - failed_count,
            failed_count=failed_count,
            candidates=tuple(results),
        )

    def _run_candidate(self, candidate: BatchCandidateRequest) -> BatchCandidateResult:
        request = candidate.backtest
        try:
            result = self._run_backtest.execute(request)
            persisted = self._persist_backtest.execute(request, result)
            accounting = result.accounting
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=result.run_id,
                instance_id=result.instance_id,
                status="completed",
                artifact_path=persisted.artifact_path,
                realised_trade_count=accounting.realised_trade_count,
                open_position_count=accounting.open_position_count,
                final_equity=accounting.final_equity,
                gross_pnl=accounting.gross_pnl,
                fees_paid=accounting.fees_paid,
                net_pnl=accounting.net_pnl,
                market_data_hash=result.strategy_evaluation.market_data_hash,
                metadata=candidate.metadata,
            )
        except Exception as exc:  # noqa: BLE001 -- failure isolation is the batch contract
            return BatchCandidateResult(
                candidate_id=candidate.candidate_id,
                run_id=request.run_id,
                instance_id=request.strategy.instance_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
                metadata=candidate.metadata,
            )
