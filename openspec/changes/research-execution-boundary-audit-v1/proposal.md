# Proposal: Research execution boundary audit v1

## Why

The legacy BBB `ema_pullback/execution` package combines strategy evaluation, managed-policy calculation, fill simulation, trade accounting, diagnostics and artifact rendering. Copying that package into the new Research Service would reintroduce strategy semantics and legacy DataFrame coupling into a greenfield service.

A function-level ownership audit is required before implementing the authoritative backtest path.

## What changes

- inventory every top-level class and function in the legacy execution package;
- classify each symbol as Strategy Engine-owned, Research Service-owned, presentation/reporting, external-service replacement or obsolete;
- define the transport-neutral boundary `StrategyEvaluationResult + MarketFrame + ExecutionPolicy -> BacktestResult`;
- define the first production module layout for execution, accounting and artifacts;
- identify frozen parity scenarios required before implementation;
- update the master plan so the next implementation is a direct authoritative Research Service path with no runtime legacy execution.

## Non-goals

- no production simulator is implemented in this change;
- no legacy module is imported into `src/research_service`;
- no backtest API route is activated;
- no partial exits, pyramiding or portfolio-level multi-position semantics are introduced.
