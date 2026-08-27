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
from research_service.api.contracts.managed_policy_events import ManagedPolicyEventTrace
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
from research_service.domain.errors import InvalidRequest, RunAlreadyExists
from research_service.execution.managed_policy_events import ManagedPolicyEvent
from research_service.runtime.services import services

router = APIRouter(prefix="/api/research", tags=["research"])


def _resolve_end_ms(to_ms: int | None, to_open_time_ms: int | None) -> int:
    """Resolve the diagnostics-route exclusive end, preferring an explicit bar edge."""

    if to_open_time_ms is not None:
        return to_open_time_ms
    if to_ms is not None:
        return to_ms
    raise InvalidRequest("provide to or to_open_time_ms")


@router.get("/component-catalog", response_model=ComponentCatalog)
def component_catalog(
    request: Request,
    family: str = Query(default="ema_pullback"),
) -> ComponentCatalog:
    return services(request).component_catalog.execute(family=family)


@router.post("/config/validate", response_model=ValidationResult)
def validate_config(request: Request, draft: StrategyConfigDraft) -> ValidationResult:
    return services(request).config_validation.execute(draft)


@router.post("/config/serialize", response_model=SerializeResult)
def serialize_config(
    request: Request,
    draft: StrategyConfigDraft,
    format: str = Query(default="json"),
) -> SerializeResult:
    return services(request).research_configs.serialize(draft, format)


@router.post("/config/save", response_model=SaveConfigResult)
def save_config(request: Request, payload: SaveConfigRequest) -> SaveConfigResult:
    return services(request).research_configs.save(payload.draft)


@router.get("/configs/state", response_model=ConfigStateResponse)
def config_state(
    request: Request,
    family: str = Query(default="ema_pullback"),
) -> ConfigStateResponse:
    return services(request).research_configs.state(family)


@router.put("/configs/selected", response_model=ConfigStateResponse)
def select_config(
    request: Request,
    payload: SelectConfigRequest,
) -> ConfigStateResponse:
    return services(request).research_configs.select(payload)


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

    managed_policy_events: list[ManagedPolicyEvent] = []
    result = services(request).run_single_instance_backtest.execute(
        payload,
        managed_policy_events_sink=managed_policy_events,
    )
    try:
        persisted = services(request).persist_single_instance_backtest.execute(
            payload,
            result,
            tuple(managed_policy_events),
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
    return list(services(request).read_research_runs.list_runs())


@router.get("/runs/latest", response_model=RunDetail)
def latest_run(request: Request) -> RunDetail:
    return services(request).read_research_runs.latest()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(request: Request, run_id: str) -> RunDetail:
    return services(request).read_research_runs.detail(run_id)


@router.get("/runs/{run_id}/summary", response_model=RunCompactSummary)
def get_run_summary(request: Request, run_id: str) -> RunCompactSummary:
    return services(request).read_research_runs.compact_summary(run_id)


@router.get("/runs/{run_id}/trades", response_model=RunTrades)
def get_run_trades(request: Request, run_id: str) -> RunTrades:
    return services(request).read_research_runs.trades(run_id)


@router.get("/runs/{run_id}/metrics", response_model=RunMetrics)
def get_run_metrics(request: Request, run_id: str) -> RunMetrics:
    return services(request).read_research_runs.metrics(run_id)


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
    end_ms = _resolve_end_ms(to_ms, to_open_time_ms)
    return services(request).project_run_diagnostics.signal_trace(
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
    end_ms = _resolve_end_ms(to_ms, to_open_time_ms)
    return services(request).project_run_diagnostics.chart_events(
        run_id=run_id,
        variant=variant,
        from_ms=from_ms,
        to_ms=end_ms,
        context_overlay_ref=context_overlay_ref,
    )


@router.get("/runs/{run_id}/managed-policy-events", response_model=ManagedPolicyEventTrace)
def get_run_managed_policy_events(
    request: Request,
    run_id: str,
    position_id: str | None = Query(None, min_length=1),
) -> ManagedPolicyEventTrace:
    return services(request).project_run_diagnostics.managed_policy_events(
        run_id=run_id,
        position_id=position_id,
    )
