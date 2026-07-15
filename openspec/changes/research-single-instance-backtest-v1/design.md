# Design

`RunSingleInstanceBacktest` calls `StrategyEnginePort.evaluate_range`, reads the same range through `MarketDataPort`, applies the execution-contract acceptance gate, runs `run_unified_execution_loop`, and accounts the result with `account_execution_loop`.

Managed replay is provided to the loop through a closure over the original strategy request. The application layer remains transport-neutral and does not import FastAPI or concrete HTTP clients.
