"""``/api/market`` endpoints — candles and indicators."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from research_api.contracts.chart import (
    CandlesWindowBundle,
    ChartBar,
    ChartMarketBundle,
    EmaWindowBundle,
    IndicatorPoint,
)
from research_api.services.chart_ema_cache import CANONICAL_ORIGIN_POLICY
from research_api.services.market_params import MarketParamError
from research_api.services.market_reader import (
    MarketDataNotFoundError,
    fetch_candles_window,
    fetch_chart_bars,
    fetch_chart_market_bundle,
    fetch_ema_points,
    fetch_ema_window,
    resolve_exclusive_to_ms,
)

router = APIRouter(prefix="/api/market", tags=["market"])


def _http_from_market(exc: Exception) -> HTTPException:
    if isinstance(exc, MarketDataNotFoundError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, MarketParamError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _range_end_ms(
    *,
    timeframe: str,
    to_ms: int | None,
    to_open_time_ms: int | None,
) -> int:
    return resolve_exclusive_to_ms(
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
        timeframe=timeframe,
    )


@router.get(
    "/chart-bundle",
    response_model=ChartMarketBundle,
    summary="[LEGACY] OHLC + anchor-stack EMAs (full-range monolithic bundle)",
    description=(
        "**Legacy** Workbench payload — prefer ``GET /candles-window`` and "
        "``GET /ema-window`` for cold load. One SQLite ``range_get`` for candles, "
        "then three in-process chart overlay EMAs (fast/anchor/slow) from candle "
        "closes. Retained for debug and rollback only; frontend cold path does "
        "not use this endpoint after market-bundle-cold-load-optimization."
    ),
    deprecated=True,
)
def get_chart_bundle(
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    ema_fast: int = Query(..., ge=1, le=5000),
    ema_anchor: int = Query(..., ge=1, le=5000),
    ema_slow: int = Query(..., ge=1, le=5000),
) -> ChartMarketBundle:
    try:
        end_ms = _range_end_ms(timeframe=timeframe, to_ms=to_ms, to_open_time_ms=to_open_time_ms)
        return fetch_chart_market_bundle(
            symbol=symbol,
            timeframe=timeframe,
            from_ms=from_ms,
            to_ms=end_ms,
            ema_fast=ema_fast,
            ema_anchor=ema_anchor,
            ema_slow=ema_slow,
        )
    except Exception as exc:
        raise _http_from_market(exc) from exc


@router.get(
    "/candles-window",
    response_model=CandlesWindowBundle,
    summary="Windowed OHLC candles with coverage metadata",
    description=(
        "Display-window candles only for Workbench cold load. "
        "Returns ``candles`` and ``coverage`` for the requested half-open range."
    ),
)
def get_candles_window(
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
) -> CandlesWindowBundle:
    try:
        end_ms = _range_end_ms(timeframe=timeframe, to_ms=to_ms, to_open_time_ms=to_open_time_ms)
        return fetch_candles_window(
            symbol=symbol,
            timeframe=timeframe,
            from_ms=from_ms,
            to_ms=end_ms,
        )
    except Exception as exc:
        raise _http_from_market(exc) from exc


@router.get(
    "/ema-window",
    response_model=EmaWindowBundle,
    summary="Windowed canonical chart overlay EMA with cache metadata",
    description=(
        "One EMA period per request. Canonical series is cached in-process; "
        "response includes ``coverage.calculation_origin_ms``, ``coverage_to_ms``, "
        "and ``cache_hit``."
    ),
)
def get_ema_window(
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    period: int = Query(..., ge=1, le=5000),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
    origin_policy: str = Query(
        CANONICAL_ORIGIN_POLICY,
        description="v1 supports canonical full-series EMA cache only.",
    ),
) -> EmaWindowBundle:
    try:
        end_ms = _range_end_ms(timeframe=timeframe, to_ms=to_ms, to_open_time_ms=to_open_time_ms)
        return fetch_ema_window(
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            from_ms=from_ms,
            to_ms=end_ms,
            origin_policy=origin_policy,
        )
    except Exception as exc:
        raise _http_from_market(exc) from exc


@router.get("/candles", response_model=list[ChartBar])
def get_candles(
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
) -> list[ChartBar]:
    try:
        end_ms = _range_end_ms(timeframe=timeframe, to_ms=to_ms, to_open_time_ms=to_open_time_ms)
        return fetch_chart_bars(
            symbol=symbol,
            timeframe=timeframe,
            from_ms=from_ms,
            to_ms=end_ms,
        )
    except Exception as exc:
        raise _http_from_market(exc) from exc


@router.get(
    "/indicators/ema",
    response_model=list[IndicatorPoint],
    summary="Chart overlay EMA (view layer)",
    description=(
        "EMA for Workbench chart visualization only. "
        "Not a research strategy feature column and not Data Engine indicator_values. "
        "Computed from closes in the requested window; narrowing `from` without warmup "
        "bars biases EMA(period)."
    ),
)
def get_ema(
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    period: int = Query(..., ge=1, le=5000),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
) -> list[IndicatorPoint]:
    try:
        end_ms = _range_end_ms(timeframe=timeframe, to_ms=to_ms, to_open_time_ms=to_open_time_ms)
        return fetch_ema_points(
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            from_ms=from_ms,
            to_ms=end_ms,
        )
    except Exception as exc:
        raise _http_from_market(exc) from exc
