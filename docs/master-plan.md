# Research Service master plan

## 1. Mission

Create an independent `research_service` repository from the BBB research backend and BFF while preserving legacy BBB until final cutover.

The target service owns:

- experiment and batch orchestration;
- execution simulation and fill arbitration;
- trade construction, fees, PnL and metrics;
- run/result persistence;
- diagnostics, signal trace, chart events and reports;
- the public BFF API consumed by Research Workbench;
- HTTP clients for Strategy Engine and Market Data Service.

It does not own:

- indicator formulas or strategy decisions — `strategy_engine`;
- canonical candle storage and readiness — `market_data_service`;
- frontend rendering and browser state — `research_workbench`;
- live exchange execution — `abi_executor_bot`.

## 2. Repository topology

```text
BBB_project/
├── market_data_service/
├── strategy_engine/
├── research_service/
├── research_workbench/
└── abi_executor_bot/
```

Browser traffic is constrained to:

```text
research_workbench -> research_service BFF
```

Backend traffic is:

```text
research_service -> strategy_engine
research_service -> market_data_service
strategy_engine  -> market_data_service
```

## 3. Current BBB top-level call paths

### 3.1 Workbench run request

```text
frontend/src/api/client.ts
POST /api/research/backtests
-> research_api/routers/research_backtests.py
-> research_api/services/backtest_service.py
-> run_strategy_specs_from_config(...)
-> execution/runner.py
-> execution/backtest.py
-> result writers
-> /api/research/runs/*
```

### 3.2 Experiment batch

```text
research/experiments/cli.py
-> validate/load batch
-> BatchRunner.run(...)
-> _default_run_candidate(...)
-> run_strategy_specs_from_config_returning_paths(...)
-> execution runner/backtest
-> report JSON
-> batch summary
```

### 3.3 Workbench market window

```text
frontend fetchCandlesWindow/fetchEmaWindow
-> /api/market/*
-> research_api/routers/market.py
-> research_api/services/market_reader.py
-> legacy Db.range_get
```

### 3.4 Workbench reports and traces

```text
frontend fetchRunReport/fetchSignalTrace/fetchChartEvents
-> /api/research/runs/*
-> results_reader / signal_trace_service / chart_events_service
-> stored research artifacts + market data
```

## 4. Target run path

```text
Workbench/CLI/Batch caller
-> ResearchRunApplication
-> load and validate research request/config
-> StrategyEnginePort.evaluate_range or evaluate_range_batch
-> MarketDataPort.read_range for simulation OHLCV
-> verify market identity/hash alignment
-> ResearchExecutionSimulator
-> fills/trades/fees/PnL
-> diagnostics/report/artifacts
-> preserved BFF response
```

The Research Service must never recalculate EMA, RSI, ATR, ADX/DI, contexts, blockers, setups, triggers, entry masks, standard exits or managed policy. These arrive from Strategy Engine.

## 5. Principal seam

The current `execution/backtest.py` mixes two responsibilities:

```text
strategy evaluation
------------------ seam ------------------
execution simulation and research artifacts
```

The new boundary is:

```text
StrategyEvaluationResult
+ canonical MarketFrame
+ ExecutionAssumptions
-> ResearchExecutionResult
```

`StrategyEvaluationResult` comes from Strategy Engine. `MarketFrame` comes independently from Market Data Service because Research Service needs OHLCV for same-bar stop/take arbitration, fills, diagnostics and charts.

## 6. BFF ownership

`research_api` is ported into `src/research_service/api`. The public routes are preserved during initial cutover:

- `/api/market/candles-window`;
- `/api/market/ema-window`;
- `/api/market/chart-bundle` while legacy compatibility is needed;
- `/api/research/runs*`;
- `/api/research/backtests`;
- `/api/research/component-catalog`;
- `/api/research/config/*`;
- `/api/research/configs/*`.

The implementation behind these routes changes, not the browser contract.

## 7. External backend contracts

### 7.1 Strategy Engine

Research Service consumes:

- `POST /v1/strategy-evaluations/range`;
- `POST /v1/strategy-evaluations/range-batch`;
- `POST /v1/strategy-evaluations/managed-replay` only where compatibility replay is required;
- `GET /v1/strategies` and strategy schema/catalog routes;
- `POST /v1/indicator-evaluations/range` for chart/research indicator-only consumers.

### 7.2 Market Data Service

Research Service consumes:

- `GET /v1/candles?ticker=...&timeframe=...&from_ms=...&to_ms=...`.

Required semantics:

- canonical `.P` ticker;
- aligned half-open range;
- ready-only complete response;
- Decimal-text OHLCV;
- strict ascending complete grid;
- no partial success.

## 8. Frontend extraction

The current `frontend/` is copied into a separate `research_workbench` repository. It remains a pure browser package and uses `VITE_API_BASE_URL` to reach Research Service. No Strategy Engine or MDS URL is exposed to browser code.

## 9. Physical-copy policy

The immutable reference slice contains:

- all `research/` except generated results;
- all `research_api/`;
- all BBB tests for classification and parity;
- repository metadata;
- all `frontend/` in the separate Workbench scaffold.

Production packages must not import from `legacy_source`.

## 10. Delivery phases

### Phase 0 — boundary audit and provenance

- complete caller/function/argument/result audit;
- classify every copied source file;
- preserve SHA-256 provenance;
- freeze public BFF contract inventory.

### Phase 1 — Research Service foundation OpenSpec

- package layout;
- settings/wiring;
- FastAPI app and preserved routers;
- StrategyEnginePort and MarketDataPort;
- artifact storage ports;
- health/readiness;
- architecture guards.

### Phase 2 — Market BFF cutover

- replace direct legacy DB access with MDS client;
- preserve current chart DTOs and routes;
- verify window coverage and Decimal conversion;
- decide chart EMA path using Strategy Engine indicator API and BFF cache.

### Phase 3 — Strategy/market API integration

- consume the authoritative Strategy Engine range and managed-replay contracts;
- acquire the matching MDS market frame;
- validate contract versions, bar grids and provenance;
- never execute the disconnected BBB mirror in production.

### Phase 4 — Research execution reconstruction

- rebuild entry fills, protection, static/managed arbitration and position lifecycle below the seam;
- calculate fees, PnL, equity and trade diagnostics;
- compose the single-instance backtest use case.

### Phase 5 — Artifacts, API and experiments

- publish immutable run bundles atomically;
- expose the synchronous backtest endpoint;
- run sequential batch experiments with per-candidate failure isolation;
- expose runs, trades and metrics from the new artifact store.

### Phase 6 — Remaining Workbench backend capabilities

- project diagnostics and signal traces from Strategy evidence plus Research execution events — implemented;
- persist Research-owned config state — next;
- preserve public BFF contracts while replacing their implementation.

### Phase 7 — Deferred history identity and closure

- implement MDS coverage and warmup planning;
- make MDS the canonical owner of `market_data_hash` and require equality in Research Service;
- freeze remaining parity fixtures and remove the disconnected mirror from final distribution when safe.
