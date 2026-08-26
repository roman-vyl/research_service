"""Typed access to the use-case instances wired onto ``app.state``.

FastAPI/Starlette's ``Request.app.state`` is an untyped bag of attributes —
every access to it is ``Any`` as far as mypy is concerned, regardless of what
was actually assigned. Rather than let that ``Any`` leak into every route
handler's return type (previously ~18 separate "Returning Any" errors),
this module concentrates the one unavoidable trust boundary into a single
typed container and a single cast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request

from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    ReadResearchRuns,
    RunSingleInstanceBacktest,
)
from research_service.application.diagnostics import ProjectRunDiagnostics
from research_service.application.experiments import PersistBatchExperiment, RunBatchExperiment
from research_service.application.market import GetCandlesWindow, GetChartBundle, GetEmaWindow
from research_service.application.research import GetComponentCatalog, ValidateStrategyConfig
from research_service.application.research.config_persistence import ManageResearchConfigs


@dataclass(frozen=True, slots=True)
class AppServices:
    """The use-case instances a request handler is allowed to call."""

    candles_window: GetCandlesWindow
    ema_window: GetEmaWindow
    chart_bundle: GetChartBundle
    component_catalog: GetComponentCatalog
    config_validation: ValidateStrategyConfig
    research_configs: ManageResearchConfigs
    run_single_instance_backtest: RunSingleInstanceBacktest
    persist_single_instance_backtest: PersistSingleInstanceBacktest
    read_research_runs: ReadResearchRuns
    project_run_diagnostics: ProjectRunDiagnostics
    run_batch_experiment: RunBatchExperiment
    persist_batch_experiment: PersistBatchExperiment


def services(request: Request) -> AppServices:
    """Return the request's typed use-case container.

    ``request.app.state.services`` is ``Any`` to the type checker; the cast
    below is the one place that trusts ``create_app`` actually put an
    ``AppServices`` there, instead of every call site trusting it silently.
    """

    return cast(AppServices, request.app.state.services)
