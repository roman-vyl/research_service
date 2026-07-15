# Design

## Boundary

`research_service` owns transport composition only:

- candles: `MarketDataPort` / Market Data Service;
- EMA values: `StrategyEnginePort` / Indicator API;
- chart DTO conversion: Research Service BFF.

No EMA calculation is implemented in Research Service.

## Preserved contract

Request parameters:

- `symbol`
- `timeframe`
- `from`
- `to` or `to_open_time_ms`
- `ema_fast`
- `ema_anchor`
- `ema_slow`

Response:

- `candles: ChartBar[]`
- `ema_overlays: [{role, period, points}]`

Roles remain ordered `fast`, `anchor`, `slow`.

## Validation

The stack must satisfy:

`ema_fast < ema_anchor < ema_slow`

All periods must be in `[1, 5000]`.

## Reuse

The route composes `GetCandlesWindow` and the app-scoped `GetEmaWindow`. The latter retains its process-local canonical cache, so repeated chart-bundle calls do not repeat Strategy Engine EMA evaluations for already covered ranges.

## Known limitation

Canonical EMA origin remains the start of the first requested range until deferred `research-history-window-planning-v1` is implemented.
