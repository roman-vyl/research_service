## Why

Research executes every run bar by bar on a `MarketFrame` that holds each 5m candle as a
pydantic `Candle` with five `Decimal` fields. For the full BTCUSDT.P window
(1585132500000–1790543700000, 684,704 candles) this representation alone holds about
1.1 GB (measured with tracemalloc on research_service 9d1d629: candle objects 1,117 MB,
about 860 bytes per candle; the MDS JSON body is 86.8 MB). Together with the Engine and
MDS it does not fit the local Docker VM (7.75 GiB): on 2026-10-10 a Calculate of about
20 rows on `btcusdt_p.ema500.trailing_geometry_fee4_4d` OOM-killed research-service.

## What Changes

- `MarketFrame` keeps candles column-wise in fixed-width arrays instead of a tuple of
  `Candle` objects. Prices and volume are stored losslessly as an integer coefficient
  plus a decimal exponent per value, so the exact `Decimal` of every value, including its
  exponent (`6500` vs `6500.0`), is restored on access. No float for canonical values.
- Consumers keep reading `market_frame.candles[i].close` etc.: `candles` becomes a
  read-only sequence view that builds the `Candle` for the index asked for. Consumers
  are not rewritten.
- The MDS response is decoded straight into the arrays, without one pydantic model per
  candle. The grid check (complete, ordered, gap-free) stays.
- Engine, MDS, the wire contracts, execution and accounting semantics and the run
  artifacts do not change.

## Impact

- `domain/contracts.py` (`MarketFrame`), `adapters/http/market_data_client.py`
  (decode), and only those consumers that need more than index, length, iteration or
  slicing.
- Acceptance is exact: fresh runs of the reference runs must produce byte-identical
  trade, execution, strategy-evaluation, managed-event and metrics artifacts (run id and
  creation time aside); metric tolerance is not an acceptance criterion here.
