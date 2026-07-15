"""Compose the preserved chart bundle from MDS candles and Strategy Engine EMA."""

from __future__ import annotations

from research_service.api.contracts.chart import ChartEmaOverlay, ChartMarketBundle
from research_service.application.market.candles_window import GetCandlesWindow
from research_service.application.market.ema_window import (
    CANONICAL_ORIGIN_POLICY,
    GetEmaWindow,
)
from research_service.domain.errors import InvalidRequest


class GetChartBundle:
    """Build the legacy monolithic Workbench market payload."""

    def __init__(
        self,
        candles_window: GetCandlesWindow,
        ema_window: GetEmaWindow,
    ) -> None:
        self._candles_window = candles_window
        self._ema_window = ema_window

    def execute(
        self,
        *,
        symbol: str,
        timeframe: str,
        from_ms: int,
        to_ms: int,
        ema_fast: int,
        ema_anchor: int,
        ema_slow: int,
    ) -> ChartMarketBundle:
        periods = self._validate_periods(ema_fast, ema_anchor, ema_slow)
        candles = self._candles_window.execute(
            symbol=symbol,
            timeframe=timeframe,
            from_ms=from_ms,
            to_ms=to_ms,
        )
        overlays = []
        for role, period in zip(("fast", "anchor", "slow"), periods, strict=True):
            ema = self._ema_window.execute(
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                from_ms=from_ms,
                to_ms=to_ms,
                origin_policy=CANONICAL_ORIGIN_POLICY,
            )
            overlays.append(ChartEmaOverlay(role=role, period=period, points=ema.points))
        return ChartMarketBundle(candles=candles.candles, ema_overlays=overlays)

    @staticmethod
    def _validate_periods(fast: int, anchor: int, slow: int) -> tuple[int, int, int]:
        if any(period < 1 or period > 5000 for period in (fast, anchor, slow)):
            raise InvalidRequest("EMA periods must be between 1 and 5000")
        if not fast < anchor < slow:
            raise InvalidRequest(
                "anchor stack periods must satisfy ema_fast < ema_anchor < ema_slow"
            )
        return fast, anchor, slow
