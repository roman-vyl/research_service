"""Canonical chart overlay EMA in-memory cache for ``ema-window`` service (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from data_engine.config import Settings
from data_engine.contracts import timeframe_ms, validate_timeframe

from research_api.contracts.chart import EmaWindowBundle, EmaWindowCoverage, IndicatorPoint
from research_api.services.indicators import (
    compute_chart_overlay_ema,
    extend_chart_overlay_ema,
    slice_indicator_points_for_window,
)
from research_api.services.market_params import normalize_symbol, parse_time_range_ms
from research_api.services.market_reader import fetch_chart_bars

CANONICAL_ORIGIN_POLICY = "canonical"


@dataclass
class _CanonicalEmaEntry:
    calculation_origin_ms: int
    coverage_to_ms: int
    points: list[IndicatorPoint]


def _resolve_db_path(db_path: Path | None) -> Path:
    return db_path if db_path is not None else Settings().db_path


def market_data_identity(db_path: Path) -> str:
    """Revision token for cache invalidation on DB replace/refresh."""

    resolved = db_path.resolve()
    try:
        mtime_ns = resolved.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    return f"{resolved}:{mtime_ns}"


def _cache_key(
    *,
    symbol: str,
    timeframe: str,
    period: int,
    origin_policy: str,
    market_data_identity: str,
) -> str:
    return f"{origin_policy}:{market_data_identity}:{symbol}:{timeframe}:{period}"


def _bars_exclusive_end_ms(bars: list, tf_ms: int) -> int:
    if not bars:
        return 0
    return int(bars[-1].time * 1000) + tf_ms


def _points_exclusive_end_ms(points: list[IndicatorPoint], tf_ms: int) -> int:
    if not points:
        return 0
    return int(points[-1].time * 1000) + tf_ms


def _empty_ema_bundle(
    *,
    requested_from_ms: int,
    requested_to_ms: int,
    tf_ms: int,
) -> EmaWindowBundle:
    coverage = _ema_window_coverage(
        requested_from_ms=requested_from_ms,
        requested_to_ms=requested_to_ms,
        sliced=[],
        calculation_origin_ms=0,
        coverage_to_ms=0,
        cache_hit=False,
        tf_ms=tf_ms,
    )
    return EmaWindowBundle(points=[], coverage=coverage)


def _ema_window_coverage(
    *,
    requested_from_ms: int,
    requested_to_ms: int,
    sliced: list[IndicatorPoint],
    calculation_origin_ms: int,
    coverage_to_ms: int,
    cache_hit: bool,
    tf_ms: int,
) -> EmaWindowCoverage:
    if not sliced:
        return EmaWindowCoverage(
            requested_from_ms=requested_from_ms,
            requested_to_ms=requested_to_ms,
            actual_from_ms=requested_from_ms,
            actual_to_ms=requested_from_ms,
            calculation_origin_ms=calculation_origin_ms,
            coverage_to_ms=coverage_to_ms,
            cache_hit=cache_hit,
            truncated=True,
        )

    actual_from_ms = int(sliced[0].time * 1000)
    actual_to_ms = _points_exclusive_end_ms(sliced, tf_ms)
    truncated = actual_from_ms > requested_from_ms or actual_to_ms < requested_to_ms
    return EmaWindowCoverage(
        requested_from_ms=requested_from_ms,
        requested_to_ms=requested_to_ms,
        actual_from_ms=actual_from_ms,
        actual_to_ms=actual_to_ms,
        calculation_origin_ms=calculation_origin_ms,
        coverage_to_ms=coverage_to_ms,
        cache_hit=cache_hit,
        truncated=truncated,
    )


class ChartEmaCache:
    """Process-local canonical EMA series cache."""

    def __init__(self) -> None:
        self._entries: dict[str, _CanonicalEmaEntry] = {}

    def clear(self) -> None:
        self._entries.clear()

    def fetch_window(
        self,
        *,
        symbol: str,
        timeframe: str,
        period: int,
        from_ms: int,
        to_ms: int,
        db_path: Path | None = None,
        origin_policy: str = CANONICAL_ORIGIN_POLICY,
    ) -> EmaWindowBundle:
        if origin_policy != CANONICAL_ORIGIN_POLICY:
            raise ValueError(f"unsupported origin_policy: {origin_policy}")
        if period < 1:
            raise ValueError("period must be >= 1")

        sym = normalize_symbol(symbol)
        tf = validate_timeframe(timeframe.strip())
        tf_ms = timeframe_ms(tf)
        requested_from_ms, requested_to_ms = parse_time_range_ms(from_ms=from_ms, to_ms=to_ms)

        resolved_path = _resolve_db_path(db_path)
        identity = market_data_identity(resolved_path)
        key = _cache_key(
            symbol=sym,
            timeframe=tf,
            period=period,
            origin_policy=origin_policy,
            market_data_identity=identity,
        )

        entry = self._entries.get(key)

        if entry is not None and requested_to_ms <= entry.coverage_to_ms:
            sliced = slice_indicator_points_for_window(
                entry.points,
                from_ms=requested_from_ms,
                to_ms=requested_to_ms,
            )
            coverage = _ema_window_coverage(
                requested_from_ms=requested_from_ms,
                requested_to_ms=requested_to_ms,
                sliced=sliced,
                calculation_origin_ms=entry.calculation_origin_ms,
                coverage_to_ms=entry.coverage_to_ms,
                cache_hit=True,
                tf_ms=tf_ms,
            )
            return EmaWindowBundle(points=sliced, coverage=coverage)

        if entry is not None and requested_to_ms > entry.coverage_to_ms:
            new_bars = fetch_chart_bars(
                symbol=sym,
                timeframe=tf,
                from_ms=entry.coverage_to_ms,
                to_ms=requested_to_ms,
                db_path=db_path,
            )
            entry.points = extend_chart_overlay_ema(entry.points, new_bars, period=period)
            if new_bars:
                entry.coverage_to_ms = _bars_exclusive_end_ms(new_bars, tf_ms)
            self._entries[key] = entry
        else:
            bars = fetch_chart_bars(
                symbol=sym,
                timeframe=tf,
                from_ms=0,
                to_ms=requested_to_ms,
                db_path=db_path,
            )
            if not bars:
                return _empty_ema_bundle(
                    requested_from_ms=requested_from_ms,
                    requested_to_ms=requested_to_ms,
                    tf_ms=tf_ms,
                )
            origin_ms = int(bars[0].time * 1000)
            points = compute_chart_overlay_ema(bars, period=period)
            entry = _CanonicalEmaEntry(
                calculation_origin_ms=origin_ms,
                coverage_to_ms=_bars_exclusive_end_ms(bars, tf_ms),
                points=points,
            )
            self._entries[key] = entry

        sliced = slice_indicator_points_for_window(
            entry.points,
            from_ms=requested_from_ms,
            to_ms=requested_to_ms,
        )
        coverage = _ema_window_coverage(
            requested_from_ms=requested_from_ms,
            requested_to_ms=requested_to_ms,
            sliced=sliced,
            calculation_origin_ms=entry.calculation_origin_ms,
            coverage_to_ms=entry.coverage_to_ms,
            cache_hit=False,
            tf_ms=tf_ms,
        )
        return EmaWindowBundle(points=sliced, coverage=coverage)


_default_cache: ChartEmaCache | None = None


def get_chart_ema_cache() -> ChartEmaCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = ChartEmaCache()
    return _default_cache


def reset_chart_ema_cache_for_tests() -> ChartEmaCache:
    """Replace process cache (tests only)."""

    global _default_cache
    _default_cache = ChartEmaCache()
    return _default_cache
