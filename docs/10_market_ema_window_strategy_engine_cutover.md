# Market EMA Window → Strategy Engine cutover

`/api/market/ema-window` now preserves the BBB Workbench DTO while delegating EMA calculation to Strategy Engine.

The BFF maps `BTCUSDT` to `BTCUSDT.P`, sends one `ema` feature plan to `/v1/indicator-evaluations/range`, converts Decimal text to chart numbers, and caches the resulting points by ticker/timeframe/period.

## Compatibility status

- route/query compatibility: complete;
- response shape compatibility: complete;
- EMA formula ownership: Strategy Engine;
- process cache and suffix extension: complete;
- full-history canonical origin parity: pending an upstream earliest-available boundary.
