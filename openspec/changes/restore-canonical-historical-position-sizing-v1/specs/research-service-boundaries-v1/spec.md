## MODIFIED Requirements

### Requirement: Research Service ownership

Research Service SHALL own: research-run orchestration; canonical OHLCV acquisition for simulation; entry and exit fill execution; historical position sizing from current available equity and actual entry fill price; gap/open handling and same-bar candidate arbitration; position lifecycle; fees, slippage, PnL, equity, and metrics; trade records, artifacts, and diagnostics projection; research-specific state (saved configs, run artifacts); and the public BFF namespace consumed by the Research Workbench frontend. Strategy Engine SHALL NOT receive or derive account equity, notional, quantity, fees, or sizing policy.

#### Scenario: A capability performs execution or presentation work

- **WHEN** a capability performs fill arbitration, position sizing, position lifecycle, accounting, artifact persistence, or BFF projection
- **THEN** Research Service owns that behavior outright and no other service is consulted for its semantics.

#### Scenario: Strategy Engine provides an entry decision

- **WHEN** Strategy Engine returns a historical entry decision or executable opportunity
- **THEN** that fact contains no equity, notional, quantity, or sizing decision
- **AND** Research derives quantity only after resolving its own actual entry fill price.
