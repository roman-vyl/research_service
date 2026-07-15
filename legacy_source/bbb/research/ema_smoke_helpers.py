"""Pure helpers for EMA smoke tests (testable without vectorbt).

``candles_to_ohlcv_dataframe`` lives here (list[Candle] -> DataFrame).
"""

from __future__ import annotations

import pandas as pd

from data_engine.contracts import Candle


def candles_to_ohlcv_dataframe(candles: list[Candle]) -> pd.DataFrame:
    """Build OHLCV frame indexed by candle open time (UTC).

    Rows follow candle list order (caller must pass ASC by open_time_ms).
    """

    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    records = [
        {
            "open_time_ms": c.open_time_ms,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]
    df = pd.DataFrame.from_records(records)
    idx = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
    df = df.set_index(idx)
    return df[["open", "high", "low", "close", "volume"]]


def add_smoke_ema_columns(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    """Append local EMA columns for smoke-helper tests."""

    out = df.copy()
    close = out["close"].astype(float)
    for period in sorted({fast, slow}):
        out[f"ema_{period}"] = close.ewm(span=period, adjust=False).mean()
    return out


def smoke_cross_signals(
    df: pd.DataFrame,
    fast_col: str = "ema_20",
    slow_col: str = "ema_50",
) -> tuple[pd.Series, pd.Series]:
    """Long/exit crossover using named EMA columns for helper tests."""

    prev_fast = df[fast_col].shift(1)
    prev_slow = df[slow_col].shift(1)
    entries = ((df[fast_col] > df[slow_col]) & (prev_fast <= prev_slow)).fillna(False).astype(bool)
    exits = ((df[fast_col] < df[slow_col]) & (prev_fast >= prev_slow)).fillna(False).astype(bool)
    return entries, exits
