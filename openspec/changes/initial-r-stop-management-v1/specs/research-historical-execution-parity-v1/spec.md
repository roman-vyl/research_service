## ADDED Requirements

### Requirement: Initial-R stop production-path parity

The production historical execution path SHALL consume initial-R lock and
trailing actions from the candidate-wide managed projection without a
per-trade managed-replay request. Its observable managed events, exit
selection, fills, trade records, and aggregate results SHALL remain consistent
with the existing execution and accounting contracts.

#### Scenario: End-to-end lock execution

- **WHEN** a managed historical run reaches an initial-R lock and a later candle hits the effective stop
- **THEN** the run SHALL close through the existing managed-stop arbitration path with the projected rule id.

#### Scenario: End-to-end trailing execution

- **WHEN** a managed historical run advances an initial-R trail several times before a later candle hits it
- **THEN** the exit SHALL use the latest effective tightened stop and SHALL not use a superseded level.

#### Scenario: No per-trade replay regression

- **WHEN** a candidate produces multiple trades using either new stop formula
- **THEN** managed-replay HTTP calls SHALL remain zero and Engine evaluation calls SHALL remain constant per candidate.
