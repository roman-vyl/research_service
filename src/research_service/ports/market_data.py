"""Market Data Service consumer port."""

from __future__ import annotations

from typing import Protocol

from research_service.domain.contracts import MarketFrame, MarketRange


class MarketDataPort(Protocol):
    def get_bounds(self, *, ticker: str, timeframe: str): ...

    def audit_range(self, market: MarketRange): ...

    def read_historical_range(
        self,
        market: MarketRange,
        *,
        expected_market_data_hash: str,
    ) -> MarketFrame: ...

    def read_range(self, market: MarketRange) -> MarketFrame: ...

    def health(self) -> bool: ...
