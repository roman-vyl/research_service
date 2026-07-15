# Authoritative backtest implementation plan

## Change 1: execution contracts and adapters

Create:

```text
src/research_service/domain/backtests.py
src/research_service/domain/execution.py
src/research_service/application/backtests/strategy_evaluation_adapter.py
src/research_service/application/backtests/market_alignment.py
```

The adapter normalizes `POST /v1/strategy-evaluations/range` output into entry/standard-exit execution candidates and consumes `POST /v1/strategy-evaluations/managed-replay` for open-trade policy decisions. It must not contain indicator or strategy formulas.

## Change 2: deterministic simulator core

Create:

```text
src/research_service/execution/simulator.py
src/research_service/execution/arbitration.py
src/research_service/execution/fills.py
src/research_service/execution/position.py
```

Implement entry fill, stop/take/signal/runtime-exit candidate handling, gap policy and same-bar arbitration. Mirror the exact split of legacy `run_managed_execution_loop`: policy comes from Strategy Engine; OHLC hit detection and fills remain local.

## Change 3: accounting

Create:

```text
src/research_service/accounting/fees.py
src/research_service/accounting/pnl.py
src/research_service/accounting/equity.py
src/research_service/accounting/metrics.py
```

Do not couple accounting to FastAPI or pandas DataFrames.

## Change 4: run orchestration and artifacts

Create:

```text
src/research_service/application/backtests/run_backtest.py
src/research_service/artifacts/run_manifest.py
src/research_service/artifacts/result_writer.py
```

Flow:

1. validate request;
2. call Strategy Engine;
3. read canonical MarketFrame from MDS;
4. enforce alignment;
5. simulate;
6. account;
7. persist atomic run artifacts;
8. return run summary.

## Change 5: activate BFF endpoint

Replace the preserved `501` for:

```text
POST /api/research/backtests
```

The first endpoint runs one strategy instance. Batch experiments remain a later change.

## Frozen acceptance scenarios

- no entries;
- long entry then take profit;
- long entry then stop loss;
- short entry then take profit;
- short entry then stop loss;
- stop and take touched in the same bar;
- signal exit and stop touched in the same bar;
- gap through stop at bar open;
- break-even stop becomes active and later fills;
- lock-profit stop tightens only;
- managed take disabled;
- runtime exit;
- open trade at range end;
- fees and slippage;
- upstream/market timestamp mismatch.

Expected outcomes are frozen fixtures derived from the legacy reference and reviewed once. Production tests do not execute legacy code.


The implementation must follow `docs/19_unified_strategy_research_seam_contract.md`; it may not redefine the seam independently.
