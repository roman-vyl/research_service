# Research Service architecture overview

This is a short, human-readable orientation to the service's architecture.
Normative requirements live in `openspec/specs/`; this document does not
duplicate them in detail.

## 1. Mission

`research_service` is the independent research/backtest backend and BFF for
the Research Workbench frontend.

The service owns:

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

Full ownership boundaries and the cross-service alignment invariant are
normative in `openspec/specs/research-service-boundaries-v1/spec.md`.

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

## 3. Current run path

```text
Workbench/CLI/Batch caller
-> POST /api/research/backtests
-> RunSingleInstanceBacktest
   -> ResolveBacktestWindow (explicit_range / full_available against MDS
      stream bounds + continuity audit)
   -> StrategyEnginePort.evaluate_range on the resolved window
   -> MarketDataPort.read_historical_range on the resolved window
   -> accept_strategy_execution_contract (identity + hash verification)
   -> unified execution loop (fills, position lifecycle)
   -> accounting (fees, PnL, equity)
-> PersistSingleInstanceBacktest (atomic immutable run bundle)
-> /api/research/runs* (read-side BFF)
```

Research Service never recalculates EMA, RSI, ATR, ADX/DI, contexts,
blockers, setups, triggers, entry masks, standard exits, or managed policy —
all of that arrives from Strategy Engine as typed output.

## 4. BFF ownership

The Research Service FastAPI application owns the browser-facing routes:

- `/api/market/candles-window`, `/api/market/ema-window`;
- `/api/market/chart-bundle`, `/api/market/candles`,
  `/api/market/indicators/ema` (deprecated legacy-compatibility routes);
- `/api/research/runs*`;
- `/api/research/backtests`;
- `/api/research/component-catalog`;
- `/api/research/config/*`, `/api/research/configs/*`.

Per-route behavior is normative in each capability's `openspec/specs/`
entry.

## 5. External backend contracts

### 5.1 Strategy Engine

Research Service consumes:

- `POST /v1/strategy-evaluations/range`;
- `POST /v1/strategy-evaluations/managed-replay` (whenever a request has
  managed policy enabled, not only for compatibility replay);
- `POST /v1/indicator-evaluations/range` (EMA chart/research consumers);
- `GET /v1/strategies/{strategy_id}/composer-catalog`;
- `POST /v1/strategies/{strategy_id}/authoring-config/validate`.

### 5.2 Market Data Service

Research Service consumes:

- `GET /v1/candles` — runtime candles, used only by the BFF chart routes
  (`candles-window`, `chart-bundle`, and their compatibility aliases), never
  by backtest orchestration;
- `GET /v1/streams/{ticker}/{timeframe}/bounds` — stream bounds, used to
  resolve `range_policy=full_available`;
- `POST /v1/streams/{ticker}/{timeframe}/continuity-audits` — continuity
  audit and `market_data_hash`, used to verify every resolved backtest
  window before execution;
- `POST /v1/historical-candles` — the backtest execution frame, verified
  against the audited `market_data_hash`.

Required semantics for all of the above: canonical `.P` ticker; aligned
half-open range; ready-only complete response; Decimal-text OHLCV; strict
ascending complete grid; no partial success.

## 6. Frontend extraction

`research_workbench` is a separate repository and a pure browser package.
It reaches Research Service through `VITE_API_BASE_URL`; no Strategy Engine
or Market Data Service URL is exposed to browser code.

## 7. Current status / remaining work

All capabilities listed in `openspec/specs/` are implemented, tested, and
current truth — that is the source of truth for what exists.

What's genuinely unfinished:

- **`research-history-window-planning-v1`** (`openspec/changes/`) — the
  only active change. Research Service's own range-resolution slice
  (`explicit_range`/`full_available` against MDS bounds and continuity
  audit) is done and already reflected in
  `research-single-instance-backtest-v1`. Strategy Engine's warmup/
  `history_policy` half, and the coordinated three-service rollout, remain
  unimplemented. See that change's `tasks.md` for the full
  requirement-by-requirement status.
- Canonical EMA chart origin (`calculation_origin_ms`) still reports the
  first requested range start rather than an MDS-coverage-derived origin —
  documented as current, intentional behavior in
  `research-market-ema-window-v1`.
- Cross-service gaps not verifiable from this repository (e.g. whether
  Strategy Engine still computes `market_data_hash` locally) are tracked in
  `docs/known-gaps.md`.
