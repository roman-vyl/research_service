"""``/api/research/runs`` endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from research_api.contracts.runs import RunCompactSummaryReport, RunReport, RunSummary
from research_api.contracts.chart_events import ChartEventsBundle
from research_api.contracts.signal_trace import SignalTraceBundle
from research_api.services.chart_events_service import fetch_chart_events_bundle
from research_api.services.market_reader import MarketDataNotFoundError
from research_api.services.results_reader import (
    ResultsNotFoundError,
    UnsupportedSchemaVersionError,
    list_run_summaries,
    load_latest_run_report,
    load_run_report,
    load_run_summary_report,
)
from research_api.services.run_id import InvalidRunIdError
from research_api.services.signal_trace_service import (
    SignalTraceVariantNotFoundError,
    UnsupportedSignalTraceFamilyError,
    fetch_signal_trace_bundle,
)

router = APIRouter(prefix="/api/research", tags=["research"])


def _http_from_reader(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidRunIdError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ResultsNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, UnsupportedSchemaVersionError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, (json.JSONDecodeError, KeyError, TypeError, ValidationError)):
        return HTTPException(status_code=500, detail=f"Invalid run artifact: {exc}")
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    try:
        return list_run_summaries()
    except Exception as exc:
        raise _http_from_reader(exc) from exc


@router.get("/runs/latest", response_model=RunReport)
def get_latest_run() -> RunReport:
    try:
        return load_latest_run_report()
    except Exception as exc:
        raise _http_from_reader(exc) from exc


@router.get("/runs/{run_id}", response_model=RunReport)
def get_run(run_id: str) -> RunReport:
    try:
        return load_run_report(run_id=run_id)
    except Exception as exc:
        raise _http_from_reader(exc) from exc


@router.get("/runs/{run_id}/summary", response_model=RunCompactSummaryReport)
def get_run_summary(run_id: str) -> RunCompactSummaryReport:
    try:
        return load_run_summary_report(run_id=run_id)
    except Exception as exc:
        raise _http_from_reader(exc) from exc


@router.get(
    "/runs/{run_id}/signal-trace",
    response_model=SignalTraceBundle,
    summary="Per-bar entry pipeline trace (phase 5)",
)
def get_signal_trace(
    run_id: str,
    variant: str = Query(..., min_length=1),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    context_overlay_ref: str | None = Query(None, min_length=1),
) -> SignalTraceBundle:
    if to_ms is None and to_open_time_ms is None:
        raise HTTPException(status_code=400, detail="provide to or to_open_time_ms")
    try:
        return fetch_signal_trace_bundle(
            run_id=run_id,
            variant_key=variant,
            from_ms=from_ms,
            to_ms=to_ms,
            to_open_time_ms=to_open_time_ms,
            context_overlay_ref=context_overlay_ref,
        )
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ResultsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SignalTraceVariantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsupportedSignalTraceFamilyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/runs/{run_id}/chart-events",
    response_model=ChartEventsBundle,
    summary="Sparse chart display events (markers + HTF overlays)",
)
def get_chart_events(
    run_id: str,
    variant: str = Query(..., min_length=1),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    context_overlay_ref: str | None = Query(None, min_length=1),
) -> ChartEventsBundle:
    if to_ms is None and to_open_time_ms is None:
        raise HTTPException(status_code=400, detail="provide to or to_open_time_ms")
    try:
        return fetch_chart_events_bundle(
            run_id=run_id,
            variant_key=variant,
            from_ms=from_ms,
            to_ms=to_ms,
            to_open_time_ms=to_open_time_ms,
            context_overlay_ref=context_overlay_ref,
        )
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ResultsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SignalTraceVariantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsupportedSignalTraceFamilyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
