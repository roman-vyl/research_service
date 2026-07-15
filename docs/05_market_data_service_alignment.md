# Market Data Service alignment

## Two independent consumers

Both Strategy Engine and Research Service read canonical candles from Market Data Service:

- Strategy Engine needs candles to compute indicators and decisions;
- Research Service needs candles to perform execution simulation, fills, diagnostics and chart delivery.

## Required request

```http
GET /v1/candles?ticker=BTCUSDT.P&timeframe=5m&from_ms=<inclusive>&to_ms=<exclusive>
```

## Required response invariants

- requested ticker/timeframe echoed exactly;
- exact aligned half-open range;
- complete ordered grid;
- Decimal-text OHLCV;
- ready-only admission;
- no truncation or partial success.

## Research adapter behavior

The MDS client returns a transport-neutral `MarketFrame`. BFF chart mapping converts timestamps to seconds and Decimal values to frontend JSON numbers only at the presentation boundary.

## Cross-service consistency

Research Service must compare Strategy Engine market metadata/hash with its independently fetched MDS frame. A mismatch fails the run before simulation.

## Acceptance still required

A later integration change must run real MDS + Strategy Engine + Research Service containers and test:

- Docker DNS and environment settings;
- 409/422/500/503 mapping;
- timeout/retry policy;
- large ranges and concurrent evaluations;
- MDS restart during a request;
- identical market hashes across services.
