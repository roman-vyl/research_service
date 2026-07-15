# Execution boundary audit

## Decision

The new Research Service will not port the legacy `execution/` package as a package. It will rebuild research-owned behavior behind new contracts and consume all strategy-owned decisions from Strategy Engine.

The reference tree under `legacy_source/bbb/` remains disconnected and readable only for audit and frozen-fixture work.

## Normative mirror of the Strategy Engine audit

This audit is not a second independent decomposition. It is the Research-side projection of the same legacy methods documented by Strategy Engine. The normative one-to-one caller/callee/API mapping is in `docs/19_unified_strategy_research_seam_contract.md`.

The critical identical methods are:

- `execution/backtest.py::run_strategy_spec`;
- `execution/runner.py::run_strategy_specs_from_config`;
- `execution/data_loader.py::load_candles_once`;
- `execution/managed_execution_loop.py::run_managed_execution_loop`;
- `managed_exit_provider.py::ManagedExitProvider.get_bar_open_candidates`;
- `managed_exit_provider.py::ManagedExitProvider.update_end_of_bar_snapshot`;
- `execution/signal_trace.py::build_signal_trace_from_spec`.

For each one, Strategy Engine supplies the strategy-owned half through its existing API and Research Service implements only the execution/presentation half.

## Audited source

The audit covers 26 Python files and 284 top-level symbols under:

```text
legacy_source/bbb/research/strategies/ema_pullback/execution/
```

The complete symbol inventory is in `docs/16_execution_function_inventory.csv`.

## Main finding

The old boundary is not file-aligned. Several files mix responsibilities:

- `backtest.py` builds features/signals, invokes execution, calculates metrics and constructs result models;
- `managed_execution_loop.py` combines position lifecycle, candidate arbitration and managed-policy evaluation;
- `trade_runtime.py` combines strategy phase/policy state with research diagnostics;
- `results.py` combines trade normalization, accounting metrics, diagnostics, DTO projection and filesystem writing;
- `signal_trace.py` recalculates strategy internals while also building Workbench presentation data.

These files must be decomposed. Copying them wholesale would violate the greenfield boundary.

## File disposition

### Do not port: Strategy Engine-owned

- `signals.py`;
- `exits.py`;
- `exit_policy_candidates.py`;
- `managed_exit_provider.py`;
- `managed_components/*`;
- phase/policy evaluation portions of `trade_runtime.py`;
- strategy evidence construction portions of `signal_trace.py`.

### Replace with external service

- `data_loader.py` is replaced by `MarketDataPort` / Market Data Service.

### Rewrite as Research execution core

- actual position lifecycle portions of `managed_execution_loop.py`;
- `exit_arbitration.py`;
- actual fill-price portions of `exit_attribution.py`;
- orchestration portions of `runner.py` and `backtest.py`.

### Split into accounting, diagnostics and artifacts

- `results.py`;
- `result_models.py`;
- `trade_analyzer.py`;
- `managed_comparison.py`;
- presentation portions of `signal_trace.py` and `trade_runtime.py`;
- `report_table.py`.

## Target ownership matrix

| Concern | Owner |
|---|---|
| Indicator values and feature evidence | Strategy Engine |
| Entry decisions | Strategy Engine |
| Initial stop/take policy | Strategy Engine |
| Standard signal exits | Strategy Engine |
| Managed phase, active stop/take and runtime-exit decisions | Strategy Engine |
| Canonical OHLCV | Market Data Service |
| Entry and exit fill execution | Research Service |
| Gap/open-price handling | Research Service |
| Same-bar candidate arbitration | Research Service |
| Position lifecycle | Research Service |
| Fees, slippage and PnL | Research Service |
| Trade records and equity | Research Service |
| Diagnostics/report projection | Research Service |
| Run artifacts | Research Service |

## Critical seam

```text
StrategyEvaluationResult
+ MarketFrame
+ ExecutionPolicy
+ RunIdentity
-----------------------------
RunResearchBacktest
-----------------------------
BacktestResult
```

The Strategy Engine result describes what the strategy decided. It does not assert that an order filled. Research Service applies those decisions to canonical OHLCV and determines actual fills and trades.

## First implementation constraints

- one independent open position per strategy instance;
- long and short supported;
- no partial exits;
- no pyramiding;
- no cross-instance portfolio netting;
- end-of-bar policy decisions become executable from the next bar unless the response explicitly marks a bar-open candidate;
- candidate ordering is deterministic and part of the contract;
- all money and price values use normalized Decimal text at service boundaries.
