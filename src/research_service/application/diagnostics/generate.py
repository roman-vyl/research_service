"""Generate and persist a run's diagnostic artifact
(`research-diagnostics-projection-v1`, `compact-strategy-evaluation-
boundary-v1` I7 hard prerequisite).

A separate, explicit write operation from reading a diagnostics
projection -- calls Strategy Engine's dense diagnostic-evaluation
entrypoint (unaffected by I7's `/range` cutover) using the target run's
own already-stored provenance, validates the response's provenance
matches exactly, and persists it outside the run's immutable
manifest-tracked bundle. Idempotent: does not silently recompute an
already-generated artifact.
"""

from __future__ import annotations

from research_service.application.backtests.read_artifacts import ReadResearchRuns
from research_service.domain.contracts import (
    MarketRange,
    StrategyDiagnosticEvaluationDTO,
    StrategyEvaluationRequest,
)
from research_service.domain.errors import UpstreamServiceError
from research_service.ports.artifacts import RunArtifactStore
from research_service.ports.strategy_engine import StrategyEnginePort


class GenerateRunDiagnostics:
    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        runs: ReadResearchRuns,
        store: RunArtifactStore,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._runs = runs
        self._store = store

    def execute(self, run_id: str) -> StrategyDiagnosticEvaluationDTO:
        existing = self._runs.diagnostic_artifact(run_id)
        if existing is not None:
            # Generation is idempotent per run -- the existing artifact is
            # returned, not silently recomputed and replaced.
            return existing

        detail = self._runs.detail(run_id)
        evaluation = detail.result.strategy_evaluation
        market: MarketRange = evaluation.market
        request = StrategyEvaluationRequest(
            strategy_id=evaluation.strategy_id,
            instance_id=detail.result.instance_id,
            strategy_spec=detail.strategy_spec,
            market=market,
            expected_market_data_hash=evaluation.market_data_hash,
        )
        diagnostics = self._strategy_engine.evaluate_range_diagnostics(request)

        if (
            diagnostics.config_hash != evaluation.config_hash
            or diagnostics.market_data_hash != evaluation.market_data_hash
            or diagnostics.bar_count != evaluation.bar_count
        ):
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message=(
                    "Strategy Engine diagnostic response provenance does not match "
                    "the target run's stored provenance"
                ),
                details={
                    "run_id": run_id,
                    "expected_config_hash": evaluation.config_hash,
                    "actual_config_hash": diagnostics.config_hash,
                    "expected_market_data_hash": evaluation.market_data_hash,
                    "actual_market_data_hash": diagnostics.market_data_hash,
                    "expected_bar_count": evaluation.bar_count,
                    "actual_bar_count": diagnostics.bar_count,
                },
            )

        self._store.write_run_supplementary_file(
            run_id, "diagnostics.json", diagnostics.model_dump_json().encode("utf-8")
        )
        return diagnostics
