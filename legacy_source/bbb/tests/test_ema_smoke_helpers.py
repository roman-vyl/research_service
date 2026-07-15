"""Tests for research EMA helpers (pandas); optional vectorbt smoke."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")

from data_engine.contracts import Candle

from research.ema_smoke_helpers import (
    add_smoke_ema_columns,
    candles_to_ohlcv_dataframe,
    smoke_cross_signals,
)


def _synthetic_candles(n: int = 120) -> list[Candle]:
    out: list[Candle] = []
    base = 1_700_000_000_000  # arbitrary ms
    step = 3_600_000  # 1h
    price = 100.0
    for i in range(n):
        o = price
        c = price + 0.1 * (i % 7)
        h = max(o, c) + 0.05
        l = min(o, c) - 0.05
        out.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="1h",
                open_time_ms=base + i * step,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1.0,
            )
        )
        price = c
    return out


def test_candles_to_ohlcv_preserves_length_and_order() -> None:
    candles = _synthetic_candles(10)
    df = candles_to_ohlcv_dataframe(candles)
    assert len(df) == 10
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert not df["close"].isna().any()


def test_ema_columns_no_nan_on_finite_close() -> None:
    candles = _synthetic_candles(80)
    df = candles_to_ohlcv_dataframe(candles)
    enriched = add_smoke_ema_columns(df, fast=20, slow=50)
    assert not enriched["ema_20"].isna().any()
    assert not enriched["ema_50"].isna().any()


def test_smoke_ema_helpers_are_deterministic() -> None:
    candles = _synthetic_candles(40)
    ohlcv = candles_to_ohlcv_dataframe(candles)
    first = add_smoke_ema_columns(ohlcv, fast=20, slow=50)
    second = add_smoke_ema_columns(ohlcv, fast=20, slow=50)
    assert first["ema_20"].equals(second["ema_20"])
    e1, x1 = smoke_cross_signals(first, "ema_20", "ema_50")
    e2, x2 = smoke_cross_signals(second, "ema_20", "ema_50")
    assert e1.equals(e2)
    assert x1.equals(x2)


def test_crossover_signals_boolean_aligned() -> None:
    candles = _synthetic_candles(80)
    df = add_smoke_ema_columns(candles_to_ohlcv_dataframe(candles), fast=20, slow=50)
    entries, exits = smoke_cross_signals(df, "ema_20", "ema_50")
    assert entries.dtype == bool or entries.dtype == "bool"
    assert exits.dtype == bool or exits.dtype == "bool"
    assert len(entries) == len(df)
    assert not bool(entries.iloc[0]) and not bool(exits.iloc[0])


@pytest.mark.optional_vectorbt
def test_minimal_vectorbt_portfolio_from_signals() -> None:
    pytest.importorskip("vectorbt")
    import vectorbt as vbt

    candles = _synthetic_candles(100)
    ohlcv = candles_to_ohlcv_dataframe(candles)
    enriched = add_smoke_ema_columns(ohlcv, fast=20, slow=50)
    entries, exits = smoke_cross_signals(enriched, "ema_20", "ema_50")
    close = enriched["close"].astype(float)
    pf = vbt.Portfolio.from_signals(close, entries, exits, freq="1h")
    sharpe = float(pf.sharpe_ratio())
    max_dd = float(pf.max_drawdown())
    assert sharpe == sharpe  # not NaN
    assert max_dd == max_dd
