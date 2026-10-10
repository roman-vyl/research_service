## Why

Calculate (and any batch) runs inside one long-lived `research-service` process in a 7.75 GiB Docker VM. For
every run Research reads the whole price history of the window from Market Data Service (684,704 five-minute
candles for BTCUSDT.P) and walks it bar by bar. `MarketFrame.candles` is a tuple of `Candle` pydantic objects,
each with five `Decimal` fields: measured 1.2 GB held, 1.56 GB peak while decoding, 23 s to read. This, plus
memory not returned after a job, killed `research-service` (OOMKilled, exit 137) on 2026-10-10 during a Calculate
of about 20 strategies.

## What Changes

- `MarketFrame` keeps its candle history column-wise in fixed-width integer arrays (times, and open/high/low/
  close/volume as scaled integers with a per-value exponent) instead of one Python object per candle.
- `MarketFrame.candles` stays a read-only sequence of `Candle` (length, index including negative, slice,
  iteration): a `Candle` is built on access with the same `Decimal` values. Consumers are not rewritten.
- The Market Data Service response is decoded straight into the arrays, without 684,704 pydantic validations.
- The grid check (complete, ordered, no gaps) runs on the time array.

## Non-goals

- Strategy Engine, Market Data Service and their protocols: unchanged.
- Execution, accounting, fees, managed-policy semantics, run artifacts on disk: unchanged.
- No `float` for canonical prices.
- Reading the history once per job, releasing memory after a job, Engine call size: a separate change.

## Impact

`research_service`: `domain/contracts.py` (`MarketFrame`), `adapters/http/market_data_client.py`, tests that build
`MarketFrame` from a tuple of `Candle` keep working. Acceptance is exact trade/event parity (see tasks).
