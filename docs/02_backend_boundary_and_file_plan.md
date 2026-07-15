# Backend boundary and file plan

## Direct production-port candidates

- `research/experiments/{models,validation,storage,summary,batch_runner}.py` after replacing default candidate execution;
- `research_api/contracts/*` to preserve Workbench compatibility;
- `research_api/routers/*` with dependency injection instead of module-global services;
- result readers, run-id validation and artifact storage;
- execution fill arbitration, trade construction, accounting and report generation after function audit.

## Mixed files requiring surgery

- `execution/backtest.py` — strategy evaluation above seam, simulation below seam;
- `execution/runner.py` — config/run orchestration plus direct strategy calls;
- `execution/managed_execution_loop.py` — execution lifecycle must consume Strategy Engine managed decisions without owning policy;
- `execution/signal_trace.py` — separate stored strategy evidence from BBB recomputation;
- `execution/exit_attribution.py` — separate strategy attribution IDs from execution outcome attribution;
- `research_api/services/backtest_service.py` — BFF transport versus run application;
- `research_api/services/chart_events_service.py` and `signal_trace_service.py` — artifact adapter versus strategy recomputation.

## Replace-by-API files

- `execution/data_loader.py` -> Market Data Service client;
- `research_api/services/market_reader.py` -> Market Data Service client;
- `research_api/services/indicators.py` and `chart_ema_cache.py` -> Strategy Engine Indicator API adapter/cache policy;
- `research_api/services/component_catalog.py` -> Strategy Engine catalog adapter;
- all production imports from `research.strategies.ema_pullback.features/components/context/spec` -> Strategy Engine client contracts.

## BBB-only or archival material

- generated `research/results/` and `research/experiments/results/` are runtime artifacts, not source;
- strategy semantic modules remain only as immutable parity reference;
- Data Engine code is not copied;
- frontend source is owned by `research_workbench`.
