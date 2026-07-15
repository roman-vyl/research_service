# Entry execution v1

## Purpose

This is the first production execution slice on the Research side of the unified seam. It replaces the entry-opening portion of legacy `run_managed_execution_loop` without importing the legacy module.

## Inputs

- `StrategyEvaluationResult.entries.long` / `.short` from Strategy Engine;
- aligned `MarketFrame` from MDS;
- Research-owned `ExecutionPolicy`.

## Preserved invariants

- entry decision is evaluated on the canonical bar grid;
- long is checked before short when both are true;
- entry reference price is the signal bar close;
- only one position may be open for a strategy instance;
- a later entry decision is ignored while that position remains open.

## New explicit contract

`ExecutionPolicy.entry_slippage_rate` is adverse and side-aware:

- long fill = close × (1 + slippage);
- short fill = close × (1 - slippage).

Fees and PnL are deferred to `research-trade-accounting-v1`.
