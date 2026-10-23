"""`research-compact-market-frame-v1`: lossless columnar candles."""

from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.candle_columns import CandleColumns
from research_service.domain.contracts import Candle, MarketFrame, MarketRange

STEP = 300_000
RANGE = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=3 * STEP)


def _wire(t: int, close: str, volume: str = "0.001") -> dict[str, object]:
    return {"open_time_ms": t, "open": "6500", "high": "6500.0", "low": "6499.9", "close": close, "volume": volume}


def test_values_round_trip_exactly_including_exponent() -> None:
    columns = CandleColumns.from_wire(
        [_wire(0, "6500"), _wire(STEP, "6500.0", "0.00012345"), _wire(2 * STEP, "126150", "63941.104")]
    )
    assert [str(c.close) for c in columns] == ["6500", "6500.0", "126150"]
    assert columns[0].high.as_tuple() == Decimal("6500.0").as_tuple()
    assert columns[1].volume.as_tuple() == Decimal("0.00012345").as_tuple()
    assert columns[2].volume == Decimal("63941.104")


def test_wire_matches_candle_models() -> None:
    wire = [_wire(0, "6500"), _wire(STEP, "-0.5", "0"), _wire(2 * STEP, "7.25", "1E+3")]
    columns = CandleColumns.from_wire(wire)
    models = [Candle.model_validate(item) for item in wire]
    assert list(columns) == models
    assert [c.model_dump() for c in columns] == [m.model_dump() for m in models]
    assert [repr(c) for c in columns] == [repr(m) for m in models]
    assert [hash(c) for c in columns] == [hash(m) for m in models]
    for got, want in zip(columns, models, strict=True):
        for name in ("open", "high", "low", "close", "volume"):
            assert getattr(got, name).as_tuple() == getattr(want, name).as_tuple()


def test_sequence_access() -> None:
    columns = CandleColumns.from_wire([_wire(i * STEP, str(i)) for i in range(3)])
    assert len(columns) == 3
    assert columns[-1].open_time_ms == 2 * STEP
    assert [c.close for c in columns[1:]] == [Decimal("1"), Decimal("2")]
    assert list(columns.open_times()) == [0, STEP, 2 * STEP]
    with pytest.raises(IndexError):
        columns[3]


@pytest.mark.parametrize(
    "bad",
    [
        {"open_time_ms": 0, "open": "x", "high": "1", "low": "1", "close": "1", "volume": "1"},
        {"open_time_ms": -1, "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"},
        {"open_time_ms": 0, "open": "1", "high": "1", "low": "1", "close": "1"},
        {"open_time_ms": 0, "open": "NaN", "high": "1", "low": "1", "close": "1", "volume": "1"},
    ],
)
def test_invalid_wire_candles_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        CandleColumns.from_wire([bad])


def test_market_frame_accepts_candles_and_keeps_grid_check() -> None:
    candles = [Candle.model_validate(_wire(i * STEP, "1")) for i in range(3)]
    frame = MarketFrame(market=RANGE, candles=tuple(candles))
    assert isinstance(frame.candles, CandleColumns)
    assert frame.candles == tuple(candles)
    with pytest.raises(ValueError, match="gapped or unordered"):
        MarketFrame(market=RANGE, candles=(candles[0], candles[2], candles[1]))
    with pytest.raises(ValueError, match="incomplete"):
        MarketFrame(market=RANGE, candles=tuple(candles[:2]))
