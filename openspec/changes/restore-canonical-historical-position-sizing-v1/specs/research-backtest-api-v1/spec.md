## MODIFIED Requirements

### Requirement: Request contract

`POST /api/research/backtests` SHALL accept `SingleInstanceBacktestRequest`. `AccountingPolicy.initial_equity` SHALL seed canonical historical sizing. The request's `ExecutionPolicy` SHALL carry execution assumptions such as entry slippage but SHALL NOT expose caller-selected fixed quantity or a parallel fixed/equity sizing mode.

#### Scenario: Valid request accepted

- **WHEN** a well-formed `SingleInstanceBacktestRequest` is posted
- **THEN** the endpoint accepts it and begins orchestration.

#### Scenario: Fixed quantity is not a canonical request choice

- **WHEN** a caller constructs a canonical historical backtest request
- **THEN** it cannot select `quantity=1` or another fixed quantity as sizing semantics
- **AND** sizing is derived from `AccountingPolicy.initial_equity` and the Research-owned lifecycle.
