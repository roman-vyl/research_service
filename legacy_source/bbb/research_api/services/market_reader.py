"""Read-only market data adapter over Data Engine ``Db.range_get``."""

from __future__ import annotations

from pathlib import Path

from data_engine.config import Settings
from data_engine.contracts import Candle, TimeWindow, timeframe_ms, validate_timeframe
from data_engine.store.db import Db

from research_api.contracts.chart import (
    AnchorStackEmaRole,
    CandlesWindowBundle,
    CandlesWindowCoverage,
    ChartBar,
    ChartEmaOverlay,
    ChartMarketBundle,
    EmaWindowBundle,
    IndicatorPoint,
)
from research_api.services.indicators import compute_chart_overlay_ema
from research_api.services.market_params import MarketParamError, normalize_symbol, parse_time_range_ms


class MarketDataNotFoundError(FileNotFoundError):
    """SQLite database file is missing."""


def candle_to_chart_bar(candle: Candle) -> ChartBar:
    return ChartBar(
        time=int(candle.open_time_ms // 1000),
        open=float(candle.open),
        high=float(candle.high),
        low=float(candle.low),
        close=float(candle.close),
        volume=float(candle.volume),
    )


def _open_db(db_path: Path | None = None) -> Db:
    path = db_path if db_path is not None else Settings().db_path
    if not path.is_file():
        raise MarketDataNotFoundError(f"market database not found: {path}")
    return Db(path)


def fetch_chart_bars(
    *,
    symbol: str,
    timeframe: str,
    from_ms: int,
    to_ms: int,
    db_path: Path | None = None,
) -> list[ChartBar]:
    """Load candles for ``[from_ms, to_ms)`` using Data Engine storage."""

    sym = normalize_symbol(symbol)
    tf = validate_timeframe(timeframe.strip())
    start_ms, end_ms = parse_time_range_ms(from_ms=from_ms, to_ms=to_ms)

    db = _open_db(db_path)
    window = TimeWindow(start_ms, end_ms)
    candles = db.range_get(sym, tf, window)
    return [candle_to_chart_bar(c) for c in candles]


def _bars_exclusive_end_ms(bars: list[ChartBar], tf_ms: int) -> int:
    if not bars:
        return 0
    return int(bars[-1].time * 1000) + tf_ms


def _candles_window_coverage(
    *,
    requested_from_ms: int,
    requested_to_ms: int,
    candles: list[ChartBar],
    tf_ms: int,
) -> CandlesWindowCoverage:
    if not candles:
        return CandlesWindowCoverage(
            requested_from_ms=requested_from_ms,
            requested_to_ms=requested_to_ms,
            actual_from_ms=requested_from_ms,
            actual_to_ms=requested_from_ms,
            truncated=True,
        )

    actual_from_ms = int(candles[0].time * 1000)
    actual_to_ms = _bars_exclusive_end_ms(candles, tf_ms)
    truncated = actual_from_ms > requested_from_ms or actual_to_ms < requested_to_ms
    return CandlesWindowCoverage(
        requested_from_ms=requested_from_ms,
        requested_to_ms=requested_to_ms,
        actual_from_ms=actual_from_ms,
        actual_to_ms=actual_to_ms,
        truncated=truncated,
    )


def fetch_candles_window(
    *,
    symbol: str,
    timeframe: str,
    from_ms: int,
    to_ms: int,
    db_path: Path | None = None,
) -> CandlesWindowBundle:
    """Load display-window candles only with honest coverage metadata."""

    tf = validate_timeframe(timeframe.strip())
    tf_ms = timeframe_ms(tf)
    requested_from_ms, requested_to_ms = parse_time_range_ms(from_ms=from_ms, to_ms=to_ms)
    candles = fetch_chart_bars(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=requested_from_ms,
        to_ms=requested_to_ms,
        db_path=db_path,
    )
    coverage = _candles_window_coverage(
        requested_from_ms=requested_from_ms,
        requested_to_ms=requested_to_ms,
        candles=candles,
        tf_ms=tf_ms,
    )
    return CandlesWindowBundle(candles=candles, coverage=coverage)


def fetch_ema_window(
    *,
    symbol: str,
    timeframe: str,
    period: int,
    from_ms: int,
    to_ms: int,
    db_path: Path | None = None,
    origin_policy: str = "canonical",
    cache=None,
) -> EmaWindowBundle:
    """Canonical EMA window slice via in-memory cache (see ``chart_ema_cache``)."""

    from research_api.services.chart_ema_cache import ChartEmaCache, get_chart_ema_cache

    ema_cache: ChartEmaCache = cache if cache is not None else get_chart_ema_cache()
    return ema_cache.fetch_window(
        symbol=symbol,
        timeframe=timeframe,
        period=period,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_path,
        origin_policy=origin_policy,
    )


def _validate_anchor_stack_periods(
    ema_fast: int,
    ema_anchor: int,
    ema_slow: int,
) -> tuple[int, int, int]:
    if ema_fast < 1 or ema_anchor < 1 or ema_slow < 1:
        raise ValueError("ema_fast, ema_anchor, and ema_slow must be >= 1")
    if not (ema_fast < ema_anchor < ema_slow):
        raise ValueError("anchor stack periods must satisfy fast < anchor < slow")
    return ema_fast, ema_anchor, ema_slow


def fetch_chart_market_bundle(
    *,
    symbol: str,
    timeframe: str,
    from_ms: int,
    to_ms: int,
    ema_fast: int,
    ema_anchor: int,
    ema_slow: int,
    db_path: Path | None = None,
) -> ChartMarketBundle:
    """One ``range_get`` pass: OHLC bars + anchor-stack chart overlay EMAs.

    Overlay EMA is computed from candle closes in the requested window only —
    not research feature columns (``ema_close_*``).
    """

    fast, anchor, slow = _validate_anchor_stack_periods(ema_fast, ema_anchor, ema_slow)
    bars = fetch_chart_bars(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_path,
    )
    overlays: list[ChartEmaOverlay] = []
    for role, period in (
        ("fast", fast),
        ("anchor", anchor),
        ("slow", slow),
    ):
        overlays.append(
            ChartEmaOverlay(
                role=role,  # type: ignore[arg-type]
                period=period,
                points=compute_chart_overlay_ema(bars, period=period),
            )
        )
    return ChartMarketBundle(candles=bars, ema_overlays=overlays)


def fetch_chart_overlay_ema(
    *,
    symbol: str,
    timeframe: str,
    period: int,
    from_ms: int,
    to_ms: int,
    db_path: Path | None = None,
) -> list[IndicatorPoint]:
    """Load OHLC window from Data Engine, then compute chart overlay EMA in-process.

    Prefer ``fetch_chart_market_bundle`` when candles and anchor-stack overlays are needed.
    See ``compute_chart_overlay_ema`` for semantics and warmup limitations.
    """

    if period < 1:
        raise ValueError("period must be >= 1")
    bars = fetch_chart_bars(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_path,
    )
    return compute_chart_overlay_ema(bars, period=period)


# Back-compat alias for internal/tests naming.
fetch_ema_points = fetch_chart_overlay_ema


def exclusive_end_for_report_to(
    *,
    to_open_time_ms: int,
    timeframe: str,
) -> int:
    """Extend report ``data_range.to_open_time_ms`` for half-open ``range_get``."""

    return int(to_open_time_ms) + timeframe_ms(validate_timeframe(timeframe))


def resolve_exclusive_to_ms(
    *,
    to_ms: int | None,
    to_open_time_ms: int | None,
    timeframe: str,
) -> int:
    """Resolve half-open window end: explicit ``to`` or report ``to_open_time_ms`` + bar."""

    if to_ms is not None and to_open_time_ms is not None:
        raise MarketParamError("provide either to or to_open_time_ms, not both")
    if to_ms is not None:
        return int(to_ms)
    if to_open_time_ms is not None:
        return exclusive_end_for_report_to(to_open_time_ms=to_open_time_ms, timeframe=timeframe)
    raise MarketParamError("either to or to_open_time_ms is required")
