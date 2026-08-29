"""Backtest application use cases."""

from research_service.application.backtests.artifacts import (
    PersistedRunArtifacts,
    RunArtifactFile,
    RunArtifactManifest,
)
from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.application.backtests.from_deployable_instance import (
    build_backtest_request,
)
from research_service.application.backtests.materialize_backtest_projection import (
    MaterializeBacktestProjectionOutcome,
    SingleInstanceRunOutcome,
)
from research_service.application.backtests.persist_run import (
    ArtifactRef,
    PersistSingleInstanceRun,
    SingleInstanceRunResult,
)
from research_service.application.backtests.read_artifacts import ReadResearchRuns
from research_service.application.backtests.run_backtest import RunSingleInstanceBacktest
from research_service.application.backtests.run_views import (
    RunCompactSummary,
    RunDetail,
    RunDetailResult,
    RunSummary,
)

__all__ = [
    "ArtifactRef",
    "MaterializeBacktestProjectionOutcome",
    "PersistedRunArtifacts",
    "PersistSingleInstanceRun",
    "ReadResearchRuns",
    "build_backtest_request",
    "RunArtifactFile",
    "RunArtifactManifest",
    "RunCompactSummary",
    "RunDetail",
    "RunDetailResult",
    "RunSingleInstanceBacktest",
    "RunSummary",
    "SingleInstanceBacktestRequest",
    "SingleInstanceRunOutcome",
    "SingleInstanceRunResult",
]
