# Design

## Inputs

- aligned `StrategyEvaluationResult`;
- aligned MDS `MarketFrame`;
- Research-owned `ExecutionPolicy`;
- optional managed replay provider keyed by the newly opened `PositionState`.

The managed replay provider is a transport-neutral callback. A future backtest orchestrator will implement it through `StrategyEnginePort.evaluate_managed_replay()`. The execution loop itself does not know HTTP.

## Per-bar ordering

For each bar:

1. remember whether a position existed at bar open;
2. if it did, collect static and managed candidates and run unified arbitration;
3. close the position when a winner exists;
4. only when the bar began flat, evaluate entry at bar close;
5. resolve the managed replay once for a newly opened position;
6. never execute an exit on the same bar as entry.

A position that existed at bar open blocks replacement entry on that bar even if it closes during arbitration. This mirrors legacy `run_managed_execution_loop`.

## Outputs

- ordered `PositionExecution` records;
- deterministic `ExecutionEvent` records;
- optional `final_open_position`;
- contract version `research_execution_loop.v1`.

The loop does not synthesize a closing fill at the end of the range. An unclosed position remains explicitly open.

## Deferred

Fees, PnL, equity, MFE/MAE, trade records, artifacts and HTTP orchestration belong to subsequent changes.
