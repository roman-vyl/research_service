# Design

## Boundaries

- `/api/market/candles` delegates to `GetCandlesWindow` and returns `.candles`.
- `/api/market/indicators/ema` delegates to `GetEmaWindow` with canonical origin
  policy and returns `.points`.
- No local candle storage and no local EMA calculation are introduced.
- Both routes share the same application-scoped dependencies and EMA cache as
  the windowed routes.

## Compatibility

The request parameters and response list models remain compatible with the BBB
BFF contract. Both endpoints are marked deprecated because the windowed routes
provide explicit coverage metadata.
