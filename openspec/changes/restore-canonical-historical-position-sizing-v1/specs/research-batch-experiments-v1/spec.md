## ADDED Requirements

### Requirement: Canonical position-sizing path

Every batch candidate SHALL inherit the same current-equity historical sizing lifecycle used by a direct single-instance backtest through the shared authoritative materializer. Batch orchestration SHALL NOT calculate, override, default, or post-process quantity or equity independently.

#### Scenario: Same candidate in single and batch

- **WHEN** the same candidate, market frame, execution assumptions, accounting policy, and Strategy Engine projection are materialized directly and inside a batch
- **THEN** their entry quantities, notionals, fees, PnL, equity chain, and final equity are identical.

#### Scenario: One candidate reaches impossible financial state

- **WHEN** a candidate's canonical sizing/accounting lifecycle fails closed
- **THEN** that candidate is reported failed under existing failure isolation
- **AND** later candidates may run without inheriting its equity or state.
