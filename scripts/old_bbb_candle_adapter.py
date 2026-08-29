"""I6.A -- proof-only old-BBB input adapter
(`compact-strategy-evaluation-boundary-v1`, Master Plan).

Old BBB never calls Research's `MarketDataPort` -- it loads candles
directly from its own local store
(`research/strategies/ema_pullback/execution/data_loader.py::
load_candles_once`) into a `pandas.DataFrame` shaped by
`research/ema_smoke_helpers.py::candles_to_ohlcv_dataframe`
(`open_time_ms`-indexed, `open`/`high`/`low`/`close`/`volume` columns,
row order = candle list order, ASC by `open_time_ms`).

This function constructs that exact row-record shape directly from the
one `ResolveBacktestWindow`-resolved `MarketFrame.candles` Research's
own pipeline already fetched -- bypassing `load_candles_once`/
`data_engine.store.Db` entirely, so old BBB and the new path are
provably fed the identical frozen dataset rather than two independent
reads (`research-run-artifact-parity-v1`, "Same frozen market dataset
on both sides"). `pandas` is not a research_service dependency, so this
returns the row-records `pd.DataFrame.from_records(...)` would wrap --
the same content, without adding a new production/proof-script
dependency for a one-column-rename step old BBB's own code already
does trivially.
"""

from __future__ import annotations

from typing import Any

from research_service.domain.contracts import MarketFrame


def candles_to_ohlcv_records(frame: MarketFrame) -> list[dict[str, Any]]:
    """Row-record equivalent of `candles_to_ohlcv_dataframe(candles)` for
    `frame.candles` -- one dict per candle, in frame order (ASC by
    `open_time_ms`, matching `MarketFrame`'s own validated grid)."""

    return [
        {
            "open_time_ms": candle.open_time_ms,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in frame.candles
    ]
