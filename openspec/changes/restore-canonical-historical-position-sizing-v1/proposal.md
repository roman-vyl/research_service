# Proposal: Restore Canonical Historical Position Sizing v1

## Why

Canonical historical Research currently treats `ExecutionPolicy.quantity = 1` as position-sizing semantics. That makes PnL, fees, equity evolution, single/batch comparisons, and AutoResearch findings depend on a fixed unit rather than the capital-compounding behavior of the primary old-BBB/vectorbt path.

Research already owns fills, fees, PnL, and equity. Quantity therefore belongs in the same Research-owned historical lifecycle and must be derived from the capital available at each entry, not supplied by Strategy Engine or selected as a parallel fixed-unit canonical mode.

## What changes

- `AccountingPolicy.initial_equity` seeds one realised-equity chain per candidate run.
- Before each entry, Research resolves the actual side-aware slipped fill price and sizes a positive quantity from current available equity divided by that fill price.
- Closing PnL and entry/exit fees update equity before any later position is sized.
- Long and short use the same positive full-equity notional formula; side affects adverse entry slippage and PnL sign, not the quantity formula.
- The canonical historical request no longer exposes fixed `ExecutionPolicy.quantity` as selectable sizing semantics.
- Single-instance and batch candidates use the same materialization/lifecycle path; AutoResearch inherits it through the existing batch boundary.
- Invalid or non-positive financial state fails closed.
- Historical parity evidence is extended to cover the restored sizing/equity chain.

## Impact

Affected capabilities:

- `research-service-boundaries-v1`
- `research-backtest-api-v1`
- `research-entry-execution-v1`
- `research-trade-accounting-v1`
- `research-single-instance-backtest-v1`
- `research-batch-experiments-v1`
- `bbb-autoresearch-v1`
- `research-historical-execution-parity-v1`

Expected implementation areas are the canonical projection materializer, entry-fill construction, a Research-owned sizing service, incremental closed-trade accounting, request contracts, tests, and parity proof fixtures.

## Out of scope

- Strategy Engine changes or any Engine knowledge of equity, notional, quantity, fees, or account state.
- Portfolio allocation, leverage, margin, pyramiding, partial exits, cross-instance capital sharing, or mark-to-market equity.
- A second canonical `qty=1` mode.
- AutoResearch-specific sizing or metric logic.
- Production implementation in this OpenSpec-only change.
