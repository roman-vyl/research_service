"""Build the preserved Workbench candle-window DTO from canonical MDS data."""

from __future__ import annotations

import re

from research_service.api.contracts.chart import (
    CandlesWindowBundle,
    CandlesWindowCoverage,
    ChartBar,
)
from research_service.domain.contracts import MarketRange, timeframe_ms
from research_service.domain.errors import InvalidRequest
from research_service.ports.market_data import MarketDataPort

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,32}(?:\.P)?$")


def canonical_ticker(symbol: str) -> str:
    candidate = symbol.strip().upper()
    if not _SYMBOL_RE.fullmatch(candidate):
        raise InvalidRequest(f"Invalid symbol: {symbol!r}")
    return candidate if candidate.endswith(".P") else f"{candidate}.P"


def resolve_exclusive_to_ms(
    *,
    timeframe: str,
    to_ms: int | None,
    to_open_time_ms: int | None,
) -> int:
    if to_ms is not None and to_open_time_ms is not None:
        raise InvalidRequest("provide either to or to_open_time_ms, not both")
    if to_ms is not None:
        return int(to_ms)
    if to_open_time_ms is not None:
        try:
            step_ms = timeframe_ms(timeframe.strip())
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc
        return int(to_open_time_ms) + step_ms
    raise InvalidRequest("either to or to_open_time_ms is required")


class GetCandlesWindow:
    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data

    def execute(
        self,
        *,
        symbol: str,
        timeframe: str,
        from_ms: int,
        to_ms: int,
    ) -> CandlesWindowBundle:
        try:
            market = MarketRange(
                ticker=canonical_ticker(symbol),
                timeframe=timeframe.strip(),
                from_ms=from_ms,
                to_ms=to_ms,
            )
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc
        frame = self._market_data.read_range(market)
        bars = [
            ChartBar(
                time=candle.open_time_ms // 1000,
                open=float(candle.open),
                high=float(candle.high),
                low=float(candle.low),
                close=float(candle.close),
                volume=float(candle.volume),
            )
            for candle in frame.candles
        ]
        return CandlesWindowBundle(
            candles=bars,
            coverage=CandlesWindowCoverage(
                requested_from_ms=market.from_ms,
                requested_to_ms=market.to_ms,
                actual_from_ms=market.from_ms,
                actual_to_ms=market.to_ms,
                truncated=False,
            ),
        )
