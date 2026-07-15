# Research execution boundary audit v1 specification

## Requirements

### REQ-1: Disconnected legacy mirror

The service SHALL NOT import, load or execute `legacy_source` from production code, runtime wiring or API handlers.

### REQ-2: Strategy ownership

Research Service SHALL consume strategy decisions from Strategy Engine and SHALL NOT recalculate indicators, contexts, component masks, entries, exit policies or managed-policy state.

### REQ-3: Execution ownership

Research Service SHALL own actual fill selection, same-bar candidate arbitration, position lifecycle, fees, slippage, realised PnL and trade records.

### REQ-4: Independent market input

Research Service SHALL obtain canonical OHLCV from Market Data Service for simulation and SHALL reject mismatched ticker, timeframe, range or bar timestamps.

### REQ-5: Typed seam

The production simulator SHALL accept typed `StrategyEvaluationResult`, `MarketFrame` and `ExecutionPolicy` inputs and SHALL return a typed `BacktestResult`.

### REQ-6: No whole-file legacy port

Mixed legacy execution files SHALL be decomposed by responsibility. They SHALL NOT be copied wholesale into the production package.

### REQ-7: Deterministic arbitration

Candidate ordering and same-bar execution semantics SHALL be explicit, deterministic and covered by frozen tests.

### REQ-8: First-slice constraints

The first implementation SHALL support one independent position per strategy instance and SHALL exclude partial exits, pyramiding and cross-instance portfolio netting.
