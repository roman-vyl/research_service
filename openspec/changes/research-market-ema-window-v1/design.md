# Design: Research Market EMA Window v1

## Flow

```text
Workbench GET /api/market/ema-window
→ Research Service GetEmaWindow
→ StrategyEnginePort.evaluate_ema
→ POST /v1/indicator-evaluations/range
→ Strategy Engine Indicator Engine
→ Market Data Service
→ Decimal EMA series
→ BFF IndicatorPoint/EmaWindowCoverage
```

## Preserved contract

Query fields remain `symbol`, `timeframe`, `period`, `from`, optional `to`, optional `to_open_time_ms`, and `origin_policy=canonical`.

Response remains `{points, coverage}` with Unix seconds, numeric EMA values, `kind=chart_overlay_ema`, and the legacy coverage field names.

## Cache

Research Service owns an in-process cache keyed by canonical ticker, timeframe and period. A request entirely inside cached coverage is a cache hit. A request extending the right edge requests only the missing suffix from Strategy Engine.

## Compatibility gap

Legacy BBB seeded the canonical EMA from the earliest candle in its local SQLite database. The current MDS/Strategy Engine APIs accept only an explicit range and do not expose earliest history metadata. Therefore `calculation_origin_ms` is the first requested range start. This is explicit and must be closed by a later MDS availability-boundary contract if exact origin parity is required.
