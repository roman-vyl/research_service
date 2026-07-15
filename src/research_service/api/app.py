"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_service.api.errors import install_error_handlers
from research_service.api.routers import market, preserved, research, system
from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    ReadResearchRuns,
    RunSingleInstanceBacktest,
)
from research_service.application.experiments import PersistBatchExperiment, RunBatchExperiment
from research_service.application.diagnostics import ProjectRunDiagnostics
from research_service.application.market import GetCandlesWindow, GetChartBundle, GetEmaWindow
from research_service.adapters.config import FilesystemConfigStore
from research_service.application.research import GetComponentCatalog, ValidateStrategyConfig
from research_service.application.research.config_persistence import ManageResearchConfigs
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container, build_container


def create_app(
    settings: Settings | None = None,
    container: Container | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_container = container or build_container(resolved_settings)
    app = FastAPI(title="Research Service", version="0.1.0")
    app.state.container = resolved_container
    app.state.candles_window = GetCandlesWindow(resolved_container.market_data)
    app.state.ema_window = GetEmaWindow(resolved_container.strategy_engine)
    app.state.component_catalog = GetComponentCatalog(resolved_container.strategy_engine)
    app.state.config_validation = ValidateStrategyConfig(resolved_container.strategy_engine)
    config_store = FilesystemConfigStore(resolved_settings.configs_root)
    config_store.ensure_ready()
    app.state.research_configs = ManageResearchConfigs(
        app.state.config_validation,
        config_store,
    )
    app.state.run_single_instance_backtest = RunSingleInstanceBacktest(
        resolved_container.strategy_engine,
        resolved_container.market_data,
    )
    app.state.persist_single_instance_backtest = PersistSingleInstanceBacktest(
        resolved_container.artifacts
    )
    app.state.read_research_runs = ReadResearchRuns(resolved_container.artifacts)
    app.state.project_run_diagnostics = ProjectRunDiagnostics(app.state.read_research_runs)
    app.state.run_batch_experiment = RunBatchExperiment(
        app.state.run_single_instance_backtest,
        app.state.persist_single_instance_backtest,
    )
    app.state.persist_batch_experiment = PersistBatchExperiment(resolved_container.artifacts)
    app.state.chart_bundle = GetChartBundle(
        app.state.candles_window,
        app.state.ema_window,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(system.router)
    app.include_router(market.router)
    app.include_router(research.router)
    app.include_router(preserved.router)
    return app
