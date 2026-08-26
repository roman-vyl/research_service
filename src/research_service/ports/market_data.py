"""Market Data Service consumer port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from research_service.domain.contracts import MarketFrame, MarketRange

if TYPE_CHECKING:
    from research_service.application.backtests.history_window import (
        ContinuityAudit,
        StreamBounds,
    )


class MarketDataPort(Protocol):
    def get_bounds(self, *, ticker: str, timeframe: str) -> "StreamBounds": ...

    def audit_range(self, market: MarketRange) -> "ContinuityAudit": ...

    def read_historical_range(
        self,
        market: MarketRange,
        *,
        expected_market_data_hash: str,
    ) -> MarketFrame: ...

    def read_range(self, market: MarketRange) -> MarketFrame: ...

    def health(self) -> bool: ...
