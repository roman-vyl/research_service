"""Workbench-compatible EMA window backed by Strategy Engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from research_service.api.contracts.chart import (
    EmaWindowBundle,
    EmaWindowCoverage,
    IndicatorPoint,
)
from research_service.application.market.candles_window import canonical_ticker
from research_service.domain.contracts import MarketRange
from research_service.domain.errors import InvalidRequest
from research_service.ports.strategy_engine import StrategyEnginePort

CANONICAL_ORIGIN_POLICY = "canonical"


@dataclass(slots=True)
class _CacheEntry:
    origin_ms: int
    coverage_to_ms: int
    points: tuple[IndicatorPoint, ...]


class GetEmaWindow:
    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine
        self._cache: dict[tuple[str, str, int], _CacheEntry] = {}

    def execute(
        self,
        *,
        symbol: str,
        timeframe: str,
        period: int,
        from_ms: int,
        to_ms: int,
        origin_policy: str,
    ) -> EmaWindowBundle:
        if origin_policy != CANONICAL_ORIGIN_POLICY:
            raise InvalidRequest(f"unsupported origin_policy: {origin_policy}")
        if period < 1 or period > 5000:
            raise InvalidRequest("period must be between 1 and 5000")
        ticker = canonical_ticker(symbol)
        try:
            requested = MarketRange(
                ticker=ticker,
                timeframe=timeframe,
                from_ms=from_ms,
                to_ms=to_ms,
            )
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc
        key = (ticker, timeframe, period)
        entry = self._cache.get(key)
        cache_hit = entry is not None and to_ms <= entry.coverage_to_ms
        if entry is None:
            result = self._strategy_engine.evaluate_ema(requested, period=period)
            entry = _CacheEntry(
                origin_ms=from_ms,
                coverage_to_ms=to_ms,
                points=_points(result.time_ms, result.values),
            )
            self._cache[key] = entry
        elif to_ms > entry.coverage_to_ms:
            extension = MarketRange(
                ticker=ticker,
                timeframe=timeframe,
                from_ms=entry.coverage_to_ms,
                to_ms=to_ms,
            )
            result = self._strategy_engine.evaluate_ema(extension, period=period)
            entry = _CacheEntry(
                origin_ms=entry.origin_ms,
                coverage_to_ms=to_ms,
                points=entry.points + _points(result.time_ms, result.values),
            )
            self._cache[key] = entry

        sliced = tuple(point for point in entry.points if from_ms <= point.time * 1000 < to_ms)
        actual_from = sliced[0].time * 1000 if sliced else from_ms
        actual_to = sliced[-1].time * 1000 + requested.step_ms if sliced else from_ms
        return EmaWindowBundle(
            points=list(sliced),
            coverage=EmaWindowCoverage(
                requested_from_ms=from_ms,
                requested_to_ms=to_ms,
                actual_from_ms=actual_from,
                actual_to_ms=actual_to,
                calculation_origin_ms=entry.origin_ms,
                coverage_to_ms=entry.coverage_to_ms,
                cache_hit=cache_hit,
                truncated=actual_from > from_ms or actual_to < to_ms,
            ),
        )


def _points(
    time_ms: tuple[int, ...],
    values: tuple[str | None, ...],
) -> tuple[IndicatorPoint, ...]:
    return tuple(
        IndicatorPoint(time=time // 1000, value=float(Decimal(value)))
        for time, value in zip(time_ms, values, strict=True)
        if value is not None
    )
