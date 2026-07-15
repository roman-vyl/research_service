# Pipeline debug instrumentation

Opt-in step counters and timings for the ema_pullback path (config → backtest → signal trace) and Workbench network loads.

## Python

**Windows (лог в `debug/reports/`):**

```bat
debug\run-pipeline-debug.bat
```

**Вручную:**

```powershell
$env:EMA_PIPELINE_DEBUG = "1"
python research/diagnostics/run_pipeline_debug.py
```

Tables print to **stderr** per `dbg_root` (e.g. `bff.backtest`, `bff.signal_trace`). Rows prefixed with **`REPEAT`** ran more than once inside that root (e.g. double config load on Workbench backtest: preflight + run).

Module API: `research.diagnostics.pipeline_trace` — `dbg_root`, `dbg_span`, `dbg_mark`, `dbg_flush`.

## Frontend (Workbench)

Три слоя — [`debug/README.md`](../../debug/README.md):

1. **Module** — `pipelineDebug.ts`; start via `scripts\dev-workbench-debug-mode.bat` (or `.env.local`); no-op when off  
2. **Console** — UI scenario → `__pipelineDebugFlush("scenario")` → table  
3. **Manual file** — `copy(JSON.stringify(__pipelineDebugExport()))` → `debug/reports/` (no auto write)

## OpenSpec

Change: [`openspec/changes/pipeline-debug-instrumentation-v1/`](../../openspec/changes/pipeline-debug-instrumentation-v1/).

## Known findings (see design.md)

- `POST /backtests` path loads external config **twice** (`_validate_config_file` + runner).
- Signal trace CLI second fetch may fail until `SignalTraceMeta` supports multi-setup `component_ids.setups`.
