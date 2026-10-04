"""Workbench-compatible EMA window backed by Strategy Engine."""

from __future__ import annotations

import logging
import math
from array import array
from bisect import bisect_left
from dataclasses import dataclass
from decimal import Decimal
from threading import Condition, Thread
from types import MappingProxyType
from typing import Literal, Mapping

from research_service.api.contracts.chart import (
    EmaWindowBundle,
    EmaWindowCoverage,
    IndicatorPoint,
)
from research_service.application.market.candles_window import canonical_ticker
from research_service.domain.contracts import MarketRange, timeframe_ms
from research_service.domain.errors import InvalidRequest, UpstreamServiceError
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import (
    MultiIndicatorSeriesResult,
    StrategyEnginePort,
)

CANONICAL_ORIGIN_POLICY = "canonical"
EMA_STACK_PERIODS = (200, 500, 1000)
PREVIEW_WARMUP_BARS = 5 * max(EMA_STACK_PERIODS)

_LOGGER = logging.getLogger(__name__)
_EntryState = Literal["preview", "full"]
_CacheKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    state: _EntryState
    origin_ms: int
    coverage_to_ms: int
    times: array[int]
    values_by_period: Mapping[int, array[float]]


class GetEmaWindow:
    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        market_data: MarketDataPort,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._market_data = market_data
        self._entries: dict[_CacheKey, _CacheEntry] = {}
        self._previewing: set[_CacheKey] = set()
        self._building_full: set[_CacheKey] = set()
        self._condition = Condition()

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
        requested = self._validate_request(
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            from_ms=from_ms,
            to_ms=to_ms,
            origin_policy=origin_policy,
        )
        if period not in EMA_STACK_PERIODS:
            return self._one_off_preview(requested, period)

        key = (requested.ticker, requested.timeframe)
        entry, owns_preview, start_full = self._acquire_entry(key)
        if start_full:
            self._start_full_build(key, requested.ticker, requested.timeframe)
        if entry is not None:
            return _slice_entry(entry, requested, period, cache_hit=True)

        preview_range = _with_warmup(requested, PREVIEW_WARMUP_BARS)
        try:
            result = self._strategy_engine.evaluate_emas(
                preview_range,
                periods=EMA_STACK_PERIODS,
            )
            preview = _compact_entry(
                result,
                state="preview",
                origin_ms=preview_range.from_ms,
                coverage_to_ms=preview_range.to_ms,
            )
        except Exception:
            with self._condition:
                self._previewing.discard(key)
                self._condition.notify_all()
            raise

        with self._condition:
            if key not in self._entries:
                self._entries[key] = preview
            self._previewing.discard(key)
            self._condition.notify_all()

        if not owns_preview:  # pragma: no cover - guarded by _acquire_entry
            raise RuntimeError("preview ownership was lost")
        return _slice_entry(preview, requested, period, cache_hit=False)

    def _validate_request(
        self,
        *,
        symbol: str,
        timeframe: str,
        period: int,
        from_ms: int,
        to_ms: int,
        origin_policy: str,
    ) -> MarketRange:
        if origin_policy != CANONICAL_ORIGIN_POLICY:
            raise InvalidRequest(f"unsupported origin_policy: {origin_policy}")
        if period < 1 or period > 5000:
            raise InvalidRequest("period must be between 1 and 5000")
        try:
            return MarketRange(
                ticker=canonical_ticker(symbol),
                timeframe=timeframe,
                from_ms=from_ms,
                to_ms=to_ms,
            )
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc

    def _acquire_entry(
        self,
        key: _CacheKey,
    ) -> tuple[_CacheEntry | None, bool, bool]:
        while True:
            with self._condition:
                entry = self._entries.get(key)
                start_full = entry is None or entry.state == "preview"
                start_full = start_full and key not in self._building_full
                if start_full:
                    self._building_full.add(key)
                if entry is not None:
                    return entry, False, start_full
                if key not in self._previewing:
                    self._previewing.add(key)
                    return None, True, start_full
                self._condition.wait()

    def _start_full_build(self, key: _CacheKey, ticker: str, timeframe: str) -> None:
        Thread(
            target=self._build_full,
            args=(key, ticker, timeframe),
            name=f"ema-full-{ticker}-{timeframe}",
            daemon=True,
        ).start()

    def _build_full(self, key: _CacheKey, ticker: str, timeframe: str) -> None:
        try:
            bounds = self._market_data.get_bounds(ticker=ticker, timeframe=timeframe)
            full_range = MarketRange(
                ticker=ticker,
                timeframe=timeframe,
                from_ms=bounds.earliest_open_time_ms,
                to_ms=bounds.latest_open_time_ms + timeframe_ms(timeframe),
            )
            result = self._strategy_engine.evaluate_emas(
                full_range,
                periods=EMA_STACK_PERIODS,
            )
            full = _compact_entry(
                result,
                state="full",
                origin_ms=full_range.from_ms,
                coverage_to_ms=full_range.to_ms,
            )
        except Exception:
            _LOGGER.exception("EMA full-history build failed for %s %s", ticker, timeframe)
        else:
            with self._condition:
                self._entries[key] = full
                self._condition.notify_all()
        finally:
            with self._condition:
                self._building_full.discard(key)
                self._condition.notify_all()

    def _one_off_preview(self, requested: MarketRange, period: int) -> EmaWindowBundle:
        preview_range = _with_warmup(requested, 5 * period)
        result = self._strategy_engine.evaluate_ema(preview_range, period=period)
        multi_result = MultiIndicatorSeriesResult(
            time_ms=result.time_ms,
            values_by_period={period: result.values},
            plan_hash=result.plan_hash,
            market_data_hash=result.market_data_hash,
        )
        preview = _compact_entry(
            multi_result,
            state="preview",
            origin_ms=preview_range.from_ms,
            coverage_to_ms=preview_range.to_ms,
        )
        return _slice_entry(preview, requested, period, cache_hit=False)


def _with_warmup(requested: MarketRange, bars: int) -> MarketRange:
    return MarketRange(
        ticker=requested.ticker,
        timeframe=requested.timeframe,
        from_ms=max(0, requested.from_ms - bars * requested.step_ms),
        to_ms=requested.to_ms,
    )


def _compact_entry(
    result: MultiIndicatorSeriesResult,
    *,
    state: _EntryState,
    origin_ms: int,
    coverage_to_ms: int,
) -> _CacheEntry:
    times = array("q", (time_ms // 1000 for time_ms in result.time_ms))
    values_by_period: dict[int, array[float]] = {}
    for period, raw_values in result.values_by_period.items():
        if len(raw_values) != len(times):
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine indicator series length mismatch",
            )
        values_by_period[period] = array(
            "d",
            (math.nan if value is None else float(Decimal(value)) for value in raw_values),
        )
    return _CacheEntry(
        state=state,
        origin_ms=origin_ms,
        coverage_to_ms=coverage_to_ms,
        times=times,
        values_by_period=MappingProxyType(values_by_period),
    )


def _slice_entry(
    entry: _CacheEntry,
    requested: MarketRange,
    period: int,
    *,
    cache_hit: bool,
) -> EmaWindowBundle:
    start = bisect_left(entry.times, requested.from_ms // 1000)
    stop = bisect_left(entry.times, requested.to_ms // 1000)
    values = entry.values_by_period[period]
    points = [
        IndicatorPoint(time=entry.times[index], value=values[index])
        for index in range(start, stop)
        if not math.isnan(values[index])
    ]
    actual_from = points[0].time * 1000 if points else requested.from_ms
    actual_to = points[-1].time * 1000 + requested.step_ms if points else requested.from_ms
    truncated = (
        requested.from_ms < entry.origin_ms
        or requested.to_ms > entry.coverage_to_ms
        or actual_from > requested.from_ms
        or actual_to < requested.to_ms
    )
    return EmaWindowBundle(
        points=points,
        coverage=EmaWindowCoverage(
            requested_from_ms=requested.from_ms,
            requested_to_ms=requested.to_ms,
            actual_from_ms=actual_from,
            actual_to_ms=actual_to,
            calculation_origin_ms=entry.origin_ms,
            coverage_to_ms=entry.coverage_to_ms,
            cache_hit=cache_hit and not truncated,
            truncated=truncated,
        ),
    )
