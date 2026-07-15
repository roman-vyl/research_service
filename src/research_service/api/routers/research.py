"""Research BFF routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from research_service.api.contracts.backtests import BacktestRunResponse
from research_service.api.contracts.runs import (
    RunCompactSummary,
    RunDetail,
    RunMetrics,
    RunSummary,
    RunTrades,
)
from research_service.api.contracts.diagnostics import ChartEventsBundle, SignalTraceBundle
from research_service.api.contracts.catalog import ComponentCatalog
from research_service.api.contracts.config import (
    ConfigStateResponse,
    SaveConfigRequest,
    SaveConfigResult,
    SelectConfigRequest,
    SerializeResult,
    StrategyConfigDraft,
    ValidationResult,
)
from research_service.application.backtests import SingleInstanceBacktestRequest
from research_service.domain.errors import RunAlreadyExists

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/component-catalog", response_model=ComponentCatalog)
def component_catalog(
    request: Request,
    family: str = Query(default="ema_pullback"),
) -> ComponentCatalog:
    return request.app.state.component_catalog.execute(family=family)


@router.post("/config/validate", response_model=ValidationResult)
def validate_config(request: Request, draft: StrategyConfigDraft) -> ValidationResult:
    return request.app.state.config_validation.execute(draft)


@router.post("/config/serialize", response_model=SerializeResult)
def serialize_config(
    request: Request,
    draft: StrategyConfigDraft,
    format: str = Query(default="json"),
) -> SerializeResult:
    return request.app.state.research_configs.serialize(draft, format)


@router.post("/config/save", response_model=SaveConfigResult)
def save_config(request: Request, payload: SaveConfigRequest) -> SaveConfigResult:
    return request.app.state.research_configs.save(payload.draft)


@router.get("/configs/state", response_model=ConfigStateResponse)
def config_state(
    request: Request,
    family: str = Query(default="ema_pullback"),
) -> ConfigStateResponse:
    return request.app.state.research_configs.state(family)


@router.put("/configs/selected", response_model=ConfigStateResponse)
def select_config(
    request: Request,
    payload: SelectConfigRequest,
) -> ConfigStateResponse:
    return request.app.state.research_configs.select(payload)


@router.post(
    "/backtests",
    response_model=BacktestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_backtest(
    request: Request,
    payload: SingleInstanceBacktestRequest,
) -> BacktestRunResponse:
    """Run and atomically persist one authoritative single-instance backtest."""

    result = request.app.state.run_single_instance_backtest.execute(payload)
    try:
        persisted = request.app.state.persist_single_instance_backtest.execute(
            payload,
            result,
        )
    except FileExistsError as exc:
        raise RunAlreadyExists(payload.run_id) from exc

    return BacktestRunResponse(
        run_id=result.run_id,
        instance_id=result.instance_id,
        realised_trade_count=result.accounting.realised_trade_count,
        open_position_count=result.accounting.open_position_count,
        final_equity=result.accounting.final_equity,
        net_pnl=result.accounting.net_pnl,
        artifact_path=persisted.artifact_path,
        manifest_contract_version=persisted.manifest.contract_version,
        market_data_hash=persisted.manifest.market_data_hash,
    )


@router.get("/runs", response_model=list[RunSummary])
def list_runs(request: Request) -> list[RunSummary]:
    return list(request.app.state.read_research_runs.list_runs())


@router.get("/runs/latest", response_model=RunDetail)
def latest_run(request: Request) -> RunDetail:
    return request.app.state.read_research_runs.latest()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(request: Request, run_id: str) -> RunDetail:
    return request.app.state.read_research_runs.detail(run_id)


@router.get("/runs/{run_id}/summary", response_model=RunCompactSummary)
def get_run_summary(request: Request, run_id: str) -> RunCompactSummary:
    return request.app.state.read_research_runs.compact_summary(run_id)


@router.get("/runs/{run_id}/trades", response_model=RunTrades)
def get_run_trades(request: Request, run_id: str) -> RunTrades:
    return request.app.state.read_research_runs.trades(run_id)


@router.get("/runs/{run_id}/metrics", response_model=RunMetrics)
def get_run_metrics(request: Request, run_id: str) -> RunMetrics:
    return request.app.state.read_research_runs.metrics(run_id)


@router.get("/runs/{run_id}/signal-trace", response_model=SignalTraceBundle)
def get_run_signal_trace(
    request: Request,
    run_id: str,
    variant: str = Query(..., min_length=1),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    context_overlay_ref: str | None = Query(None, min_length=1),
) -> SignalTraceBundle:
    if to_ms is None and to_open_time_ms is None:
        from research_service.domain.errors import InvalidRequest

        raise InvalidRequest("provide to or to_open_time_ms")
    end_ms = to_open_time_ms if to_open_time_ms is not None else int(to_ms)
    return request.app.state.project_run_diagnostics.signal_trace(
        run_id=run_id,
        variant=variant,
        from_ms=from_ms,
        to_ms=end_ms,
        context_overlay_ref=context_overlay_ref,
    )


@router.get("/runs/{run_id}/chart-events", response_model=ChartEventsBundle)
def get_run_chart_events(
    request: Request,
    run_id: str,
    variant: str = Query(..., min_length=1),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    context_overlay_ref: str | None = Query(None, min_length=1),
) -> ChartEventsBundle:
    if to_ms is None and to_open_time_ms is None:
        from research_service.domain.errors import InvalidRequest

        raise InvalidRequest("provide to or to_open_time_ms")
    end_ms = to_open_time_ms if to_open_time_ms is not None else int(to_ms)
    return request.app.state.project_run_diagnostics.chart_events(
        run_id=run_id,
        variant=variant,
        from_ms=from_ms,
        to_ms=end_ms,
        context_overlay_ref=context_overlay_ref,
    )
