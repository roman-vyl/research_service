# Current BBB call-contract audit

## A. Synchronous Workbench backtest

### Caller

`research_api/services/backtest_service.py::_run_config_file(path)`.

### Current call

```python
run_id = run_strategy_specs_from_config(path)
```

### Input

- path under `research/experiments/configs/`;
- config contains family, market identity, strategy instances and execution assumptions.

### Return

- `run_id: str`;
- side effect: latest/run/summary artifacts written under BBB results storage.

### Target replacement

`backtest_service` calls a Research application use case, not Strategy Engine directly:

```text
RunBacktest(request)
-> StrategyEngineClient.evaluate_range[_batch]
-> MarketDataClient.read_range
-> ResearchExecutionSimulator
-> ResultStore
```

The public `POST /api/research/backtests` response remains `BacktestResult`.

## B. Batch execution

### Caller

`research/experiments/batch_runner.py::BatchRunner.run`.

### Current call

Each candidate calls `_default_run_candidate`, which imports and invokes `run_strategy_specs_from_config_returning_paths`.

### Input

- validated batch spec;
- candidate strategy config path and candidate id.

### Return

- run id;
- latest result path;
- immutable run result path;
- summary extracted from report JSON.

### Target replacement

The candidate boundary becomes a `ResearchCandidateRunner` port. Its implementation uses Strategy Engine range or range-batch plus the Research simulator. Batch scheduling and candidate failure isolation remain in Research Service.

## C. Strategy execution runner

### Caller

`execution/runner.py::run_strategy_specs_from_config`.

### Current sequence

1. load external config;
2. validate a single market across variants;
3. build execution config;
4. load candles once;
5. call `run_strategy_spec` for every spec;
6. build/write research payload.

### Target sequence

1. load research config;
2. derive canonical `.P` ticker, timeframe and range;
3. call Strategy Engine `range-batch` for variants;
4. call MDS once for simulation candles;
5. verify range/identity/hash compatibility;
6. simulate each variant;
7. write the same report contracts.

## D. Strategy/backtest mixed seam

`execution/backtest.py` currently imports strategy feature builders, signal builders, exit builders, managed policy and execution integration in one module.

The method-level split is:

```text
BEFORE SEAM
FeaturePlan / enriched frame / contexts / entries / exits / managed policy

AFTER SEAM
OHLC arbitration / position lifecycle / fills / fees / trade records / metrics
```

Everything before the seam is replaced by Strategy Engine response data. Everything after the seam is ported into Research Service.

## E. Market BFF

### Current caller

`frontend/src/api/client.ts` calls `/api/market/*`.

### Current backend

`research_api/services/market_reader.py` opens legacy `Db` and invokes `range_get`.

### Target

The same BFF route calls `MarketDataServiceClient.get_candles`. The BFF translates Decimal text and millisecond timestamps to existing `ChartBar` and coverage contracts.

## F. Chart EMA

Current chart EMA is view-layer EMA and is distinct from persisted/strategy indicators. Target options are deliberately separated:

- use Strategy Engine `indicator-evaluations/range` with a warmup-extended range;
- retain a BFF chart cache and DTO conversion;
- do not compute an undocumented third EMA implementation.

The first MDS/BFF cutover OpenSpec must select and test one canonical chart-overlay policy.

## G. Component catalog/config validation

Current `component_catalog.py` and config services import BBB strategy schemas directly.

Target:

- authoritative strategy/indicator catalog and validation come from Strategy Engine;
- Research Service preserves current Composer-facing `ComponentCatalog` and `ValidationResult` DTOs through adapters;
- config file selection and persistence remain Research Service responsibilities.

## H. Runs, trace and chart events

`results_reader`, `signal_trace_service` and `chart_events_service` read stored run artifacts and sometimes market data. These remain Research Service responsibilities, but any recomputation of strategy semantics must be removed or replaced with Strategy Engine artifacts saved at run time.
