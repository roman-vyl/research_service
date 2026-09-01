## MODIFIED Requirements

### Requirement: Execution and accounting ownership

Research Service SHALL own fill arbitration, current-equity position sizing, position lifecycle, and accounting. The authoritative materialization lifecycle SHALL seed equity from `AccountingPolicy.initial_equity`, resolve actual entry fill price before quantity, account each close before sizing a later entry, and produce one internally continuous execution/accounting result.

#### Scenario: End-to-end ownership

- **WHEN** a backtest runs to completion
- **THEN** every fill, quantity, position-state transition, fee, PnL, equity transition, and accounting figure in the result was produced by Research Service's canonical lifecycle.

#### Scenario: Sequential compounding

- **WHEN** one position closes before a later entry decision
- **THEN** the close is accounted first and the later entry is sized from the resulting current equity.
