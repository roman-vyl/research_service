# Design: Research Service foundation v1

## Architecture

```text
Research Workbench
  -> Research Service FastAPI/BFF
       -> StrategyEnginePort -> HTTP Strategy Engine
       -> MarketDataPort     -> HTTP Market Data Service
       -> ArtifactStore      -> filesystem volume
```

Production code is isolated from `legacy_source`. Runtime wiring is the only layer that selects concrete adapters.

## Preserved routes

The foundation registers the existing high-value `/api/market/*` and `/api/research/*` route paths. Until a later semantic-port change implements a route, it must return a stable `501 capability_not_ported` envelope instead of a fake success or importing legacy code.

## Readiness

`/health` proves the process is alive. `/readiness` reports Strategy Engine and Market Data Service dependency health plus artifact-store availability. The initial service is ready only when both upstream services respond successfully.

## Canonical contracts

- canonical `.P` ticker identity;
- supported textual timeframe;
- aligned half-open range `[from_ms,to_ms)`;
- Decimal OHLCV parsing;
- complete ordered candle-grid validation;
- Strategy Engine result kept transport-neutral behind a port.
