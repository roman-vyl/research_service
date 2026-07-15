# Research Service

Independent research backend and Workbench BFF extracted from BBB.

## Legacy reference source

`legacy_source/bbb/` is an immutable, disconnected mirror of the original BBB research and BFF files. It is kept only for inspection, extraction audits and frozen parity fixtures. Production code under `src/research_service/` does not import it, runtime wiring does not load it, and no request executes it. The new Research Service is built as an independent authoritative service over Strategy Engine and Market Data Service APIs.

## Current status

`research-service-foundation-v1` is implemented. The package provides:

- FastAPI application and preserved Workbench route namespace;
- Strategy Engine and Market Data Service HTTP clients behind ports;
- filesystem artifact-store boundary;
- settings, wiring, health/readiness and stable errors;
- explicit HTTP 501 for routes whose semantics have not yet been ported;
- immutable BBB reference source under `legacy_source/bbb`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
make verify
```

## Run

```bash
RESEARCH_STRATEGY_ENGINE_URL=http://127.0.0.1:8090 \
RESEARCH_MARKET_DATA_URL=http://127.0.0.1:8080 \
research-service
```

The browser talks only to Research Service. It never needs Strategy Engine or Market Data Service URLs.

## Migrated BFF capability

`GET /api/market/candles-window` is backed by Market Data Service. It preserves the BBB Workbench DTO, converts legacy `BTCUSDT` to canonical `BTCUSDT.P`, and returns only complete ready ranges. Other preserved market/research routes still return `501 capability_not_ported` until their vertical slices are implemented.

### EMA window

`GET /api/market/ema-window` is operational and delegates EMA calculation to Strategy Engine. The legacy Workbench DTO and process cache metadata are preserved. Until upstream earliest-history metadata exists, the first requested range start is reported as `calculation_origin_ms`.

## Deferred history-window planning

The cross-service change `research-history-window-planning-v1` is specified but intentionally deferred until the end of the Research Service cutover. It will add MDS coverage discovery, explicit research range policies and Strategy Engine-owned warmup expansion.


## Ported market BFF slices

- `/api/market/candles-window` -> Market Data Service
- `/api/market/ema-window` -> Strategy Engine Indicator API
- `/api/market/chart-bundle` -> composed MDS candles + Strategy Engine EMA overlays

## Ported market compatibility routes

- `GET /api/market/candles` delegates to the MDS-backed candle-window use case.
- `GET /api/market/indicators/ema` delegates to the Strategy Engine-backed EMA-window use case.
- Both are deprecated compatibility aliases and define no independent semantics.

## Component catalog

`GET /api/research/component-catalog` now proxies the authoritative Strategy Engine Composer Catalog while preserving the Workbench DTO.

## Config validation

`POST /api/research/config/validate` preserves the Workbench `{ok, errors}` contract and delegates ema_pullback instance semantics to Strategy Engine.


## Execution boundary audit

`research-execution-boundary-audit-v1` is complete. The legacy execution package will not be copied into production. Strategy calculations and managed-policy decisions remain in Strategy Engine; Research Service will newly implement fills, arbitration, position lifecycle, fees, PnL, trade records and artifacts behind the typed seam `StrategyEvaluationResult + MarketFrame + ExecutionPolicy -> BacktestResult`. Implementation now follows the staged function-by-function plan. Entry, protection, static/managed exits, the unified execution loop, accounting, single-instance orchestration, atomic run artifacts, the synchronous backtest HTTP API and sequential batch experiments are complete. The runs/results BFF read layer is complete. The next production slice is diagnostics projection.


## Normative cross-service seam

The exact mirror mapping from the legacy BBB combined modules to Strategy Engine APIs and Research Service consumers is defined in `docs/19_unified_strategy_research_seam_contract.md`.

## Strategy execution contract acceptance

The Strategy Engine range and managed-replay clients now use the real nested wire contracts and validate their per-bar alignment with MDS before simulator work begins. See `docs/20_strategy_execution_contract_acceptance.md`.

## Function-by-function rebuilding plan

The authoritative staged extraction plan is `docs/21_research_service_function_porting_plan.md`. Each legacy Python call identified by the unified seam audit is replaced by a Strategy Engine/MDS contract plus a clean Research-owned implementation. `legacy_source` is never a runtime fallback.

## Entry execution

`research-entry-execution-v1` is implemented. The new execution domain consumes `entries.long` and `entries.short` from `StrategyEvaluationResult` together with the aligned MDS `MarketFrame`, opens at the signal-bar close, preserves legacy long-before-short priority, blocks re-entry while a position is open, and supports explicit side-aware entry slippage. Executable entries are additionally gated by Strategy Engine `stop_ready`, matching the legacy `entries & stop_ready` path.


## Initial protection

`research-initial-protection-v1` is implemented. Strategy Engine remains authoritative for stop/take ratios and readiness; Research Service converts the entry-bar ratios into absolute Decimal levels and attaches immutable `InitialProtection` to the open position. Under `bbb_v1`, levels remain anchored to the signal-bar close, matching the old BBB even when explicit entry slippage changes the fill. Static and managed arbitration are implemented downstream.


## Current execution slice

`research-static-exit-arbitration-v1` is implemented: Research Service consumes initial SL/TP levels and Strategy Engine signal exits, applies BBB-compatible gap/touch fills and deterministic `stop_loss -> take_profit -> signal` same-bar priority.


## Unified exit arbitration

Static and managed candidates are combined under the exact BBB v1 priority, and the unified execution loop is implemented.


## Trade accounting

`research-trade-accounting-v1` is implemented. Closed executions are converted into immutable trade records with actual-fill notionals, entry/exit fees, side-aware gross and net PnL, realised equity progression and MFE/MAE/capture/giveback diagnostics. Positions left open at the end of the range remain unrealised.

## Single-instance backtest

The transport-neutral `RunSingleInstanceBacktest` use case now composes Strategy Engine range evaluation, MDS market acquisition, unified execution and trade accounting for one strategy instance. Atomic artifact persistence is implemented; only the public backtest endpoint remains deferred.


## Run artifacts

`research-run-artifacts-v1` is implemented. Completed single-instance results are published atomically under `var/runs/<run_id>/` with an immutable manifest, exact request/evaluation/events/trades/metrics/result JSON files and SHA-256 integrity records. Existing run IDs cannot be overwritten.


## Backtest API v1

`POST /api/research/backtests` now executes one authoritative strategy instance, atomically persists the run bundle and returns HTTP 201 with a compact `research_backtest_api.v1` completion summary. Reusing an immutable `run_id` returns HTTP 409 `run_already_exists`.


## Diagnostics projection

Immutable run bundles expose Workbench diagnostics through `/api/research/runs/{run_id}/signal-trace` and `/api/research/runs/{run_id}/chart-events`. Strategy lanes come from Strategy Engine evidence; fill/lifecycle markers come from Research execution events.
