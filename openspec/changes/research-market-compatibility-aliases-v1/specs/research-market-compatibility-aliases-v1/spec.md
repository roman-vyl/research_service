# Research market compatibility aliases v1

## Requirements

### Candle list alias

The service SHALL expose `GET /api/market/candles` with the legacy parameters
`symbol`, `timeframe`, `from`, and either `to` or `to_open_time_ms`. A successful
response SHALL be a list of `ChartBar` objects and SHALL be produced through the
canonical Market Data Service-backed candle-window use case.

### EMA list alias

The service SHALL expose `GET /api/market/indicators/ema` with the legacy
parameters `symbol`, `timeframe`, `period`, `from`, and either `to` or
`to_open_time_ms`. A successful response SHALL be a list of `IndicatorPoint`
objects and SHALL be produced through the Strategy Engine-backed EMA-window use
case using canonical origin policy.

### No duplicate semantics

The compatibility routes SHALL NOT calculate indicators, access legacy SQLite,
or define independent caching rules.

### Stable invalid range handling

Semantically invalid ranges SHALL return the Research Service
`invalid_request` error with HTTP 400.
