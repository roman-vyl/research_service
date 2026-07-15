"""Preserved Workbench market routes backed by external services."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from research_service.api.contracts.chart import (
    CandlesWindowBundle,
    ChartBar,
    ChartMarketBundle,
    EmaWindowBundle,
    IndicatorPoint,
)
from research_service.application.market import (
    CANONICAL_ORIGIN_POLICY,
    resolve_exclusive_to_ms,
)

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get(
    "/chart-bundle",
    response_model=ChartMarketBundle,
    summary="[LEGACY] OHLC + anchor-stack EMA bundle",
    deprecated=True,
)
def get_chart_bundle(
    request: Request,
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from"),
    to_ms: int | None = Query(None, alias="to"),
    to_open_time_ms: int | None = Query(None),
    ema_fast: int = Query(..., ge=1, le=5000),
    ema_anchor: int = Query(..., ge=1, le=5000),
    ema_slow: int = Query(..., ge=1, le=5000),
) -> ChartMarketBundle:
    end_ms = resolve_exclusive_to_ms(
        timeframe=timeframe,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
    )
    return request.app.state.chart_bundle.execute(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=end_ms,
        ema_fast=ema_fast,
        ema_anchor=ema_anchor,
        ema_slow=ema_slow,
    )


@router.get(
    "/candles-window",
    response_model=CandlesWindowBundle,
    summary="Windowed OHLC candles with coverage metadata",
)
def get_candles_window(
    request: Request,
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from"),
    to_ms: int | None = Query(None, alias="to"),
    to_open_time_ms: int | None = Query(None),
) -> CandlesWindowBundle:
    end_ms = resolve_exclusive_to_ms(
        timeframe=timeframe,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
    )
    return request.app.state.candles_window.execute(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=end_ms,
    )


@router.get(
    "/ema-window",
    response_model=EmaWindowBundle,
    summary="Windowed canonical chart overlay EMA with cache metadata",
)
def get_ema_window(
    request: Request,
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    period: int = Query(..., ge=1, le=5000),
    from_ms: int = Query(..., alias="from"),
    to_ms: int | None = Query(None, alias="to"),
    to_open_time_ms: int | None = Query(None),
    origin_policy: str = Query(CANONICAL_ORIGIN_POLICY),
) -> EmaWindowBundle:
    end_ms = resolve_exclusive_to_ms(
        timeframe=timeframe,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
    )
    return request.app.state.ema_window.execute(
        symbol=symbol,
        timeframe=timeframe,
        period=period,
        from_ms=from_ms,
        to_ms=end_ms,
        origin_policy=origin_policy,
    )


@router.get(
    "/candles",
    response_model=list[ChartBar],
    summary="Compatibility OHLC candle list",
    deprecated=True,
)
def get_candles(
    request: Request,
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
) -> list[ChartBar]:
    end_ms = resolve_exclusive_to_ms(
        timeframe=timeframe,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
    )
    return request.app.state.candles_window.execute(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=end_ms,
    ).candles


@router.get(
    "/indicators/ema",
    response_model=list[IndicatorPoint],
    summary="Compatibility chart overlay EMA",
    deprecated=True,
)
def get_ema(
    request: Request,
    symbol: str = Query(..., min_length=2, max_length=32),
    timeframe: str = Query(..., min_length=2, max_length=8),
    period: int = Query(..., ge=1, le=5000),
    from_ms: int = Query(..., alias="from", ge=0),
    to_ms: int | None = Query(None, alias="to", ge=1),
    to_open_time_ms: int | None = Query(None, ge=0),
) -> list[IndicatorPoint]:
    end_ms = resolve_exclusive_to_ms(
        timeframe=timeframe,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
    )
    return request.app.state.ema_window.execute(
        symbol=symbol,
        timeframe=timeframe,
        period=period,
        from_ms=from_ms,
        to_ms=end_ms,
        origin_policy=CANONICAL_ORIGIN_POLICY,
    ).points
