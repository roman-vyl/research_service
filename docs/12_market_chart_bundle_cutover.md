# Market chart-bundle cutover

The deprecated Workbench endpoint `GET /api/market/chart-bundle` is now implemented by Research Service.

## Data flow

```text
Workbench
  -> Research Service /api/market/chart-bundle
      -> Market Data Service for candles
      -> Strategy Engine Indicator API for fast/anchor/slow EMA
  <- legacy ChartMarketBundle DTO
```

Research Service performs no indicator math. It converts downstream canonical values to the existing chart DTO and preserves role ordering.

The route intentionally remains deprecated because the optimized Workbench cold path uses the separate `candles-window` and `ema-window` endpoints.

## Cache behavior

The app-scoped `GetEmaWindow` cache is shared between `ema-window` and `chart-bundle`. A repeated or overlapping bundle request can therefore reuse already materialized EMA ranges.

## Deferred origin issue

EMA calculation origin still begins at the first requested range. Full-history origin planning is tracked by `research-history-window-planning-v1` and will be implemented after the active Research Service cutover.
