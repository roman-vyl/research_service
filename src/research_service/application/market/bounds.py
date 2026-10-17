"""Committed Market Data Service bounds of one market, forwarded unchanged."""

from __future__ import annotations

from research_service.api.contracts.chart import MarketBoundsBundle
from research_service.application.market.candles_window import canonical_ticker
from research_service.domain.contracts import timeframe_ms
from research_service.domain.errors import InvalidRequest
from research_service.ports.market_data import MarketDataPort


class GetMarketBounds:
    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data

    def execute(self, *, symbol: str, timeframe: str) -> MarketBoundsBundle:
        ticker = canonical_ticker(symbol)
        frame = timeframe.strip()
        try:
            timeframe_ms(frame)
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc
        bounds = self._market_data.get_bounds(ticker=ticker, timeframe=frame)
        return MarketBoundsBundle(
            symbol=ticker,
            timeframe=frame,
            earliest_open_time_ms=bounds.earliest_open_time_ms,
            latest_open_time_ms=bounds.latest_open_time_ms,
            stream_state=bounds.stream_state,
        )
