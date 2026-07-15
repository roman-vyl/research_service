# Market compatibility aliases

The legacy Workbench endpoints are now thin adapters:

```text
GET /api/market/candles
  -> GetCandlesWindow
  -> Market Data Service
  -> list[ChartBar]

GET /api/market/indicators/ema
  -> GetEmaWindow
  -> Strategy Engine Indicator API
  -> list[IndicatorPoint]
```

They intentionally omit the coverage metadata exposed by `candles-window` and
`ema-window`. Both aliases reuse the same application-scoped services, including
the EMA cache. They are retained for compatibility and marked deprecated.
