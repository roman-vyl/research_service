"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_service.adapters.config import FilesystemConfigStore
from research_service.api.errors import install_error_handlers
from research_service.api.routers import market, research, system
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
from research_service.runtime.services import AppServices
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
    app.state.services = _build_services(resolved_settings, resolved_container)
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
    return app


def _build_services(settings: Settings, container: Container) -> AppServices:
    candles_window = GetCandlesWindow(container.market_data)
    ema_window = GetEmaWindow(container.strategy_engine)
    config_validation = ValidateStrategyConfig(container.strategy_engine)
    config_store = FilesystemConfigStore(settings.configs_root)
    config_store.ensure_ready()
    run_single_instance_backtest = RunSingleInstanceBacktest(
        container.strategy_engine,
        container.market_data,
    )
    persist_single_instance_backtest = PersistSingleInstanceBacktest(container.artifacts)
    read_research_runs = ReadResearchRuns(container.artifacts)
    return AppServices(
        candles_window=candles_window,
        ema_window=ema_window,
        chart_bundle=GetChartBundle(candles_window, ema_window),
        component_catalog=GetComponentCatalog(container.strategy_engine),
        config_validation=config_validation,
        research_configs=ManageResearchConfigs(config_validation, config_store),
        run_single_instance_backtest=run_single_instance_backtest,
        persist_single_instance_backtest=persist_single_instance_backtest,
        read_research_runs=read_research_runs,
        project_run_diagnostics=ProjectRunDiagnostics(read_research_runs),
        run_batch_experiment=RunBatchExperiment(
            run_single_instance_backtest,
            persist_single_instance_backtest,
        ),
        persist_batch_experiment=PersistBatchExperiment(container.artifacts),
    )
