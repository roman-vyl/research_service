from decimal import Decimal

import pytest
from pydantic import ValidationError

from research_service.domain.contracts import Candle, MarketFrame, MarketRange


def test_market_range_requires_canonical_aligned_half_open_window() -> None:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000)
    assert market.step_ms == 300_000
    with pytest.raises(ValidationError):
        MarketRange(ticker="BTCUSDT", timeframe="5m", from_ms=0, to_ms=600_000)
    with pytest.raises(ValidationError):
        MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=1, to_ms=600_000)


def test_market_frame_requires_complete_ordered_grid() -> None:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="1m", from_ms=0, to_ms=120_000)
    candles = tuple(
        Candle(
            open_time_ms=value,
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("1"),
            close=Decimal("1.5"),
            volume=Decimal("10"),
        )
        for value in (0, 60_000)
    )
    assert len(MarketFrame(market=market, candles=candles).candles) == 2
    with pytest.raises(ValidationError):
        MarketFrame(market=market, candles=candles[:1])
