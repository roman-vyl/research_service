## MODIFIED Requirements

### Requirement: Side-aware levels

Long and short stop/take levels SHALL use the reviewed legacy formulas and
SHALL reject invalid non-positive prices. A non-positive initial take price SHALL
be rejected as unreachable take-profit, and the entry SHALL NOT be opened.

#### Scenario: Non-positive derived price

- **WHEN** a derived stop or take price would be zero or negative
- **THEN** `InitialProtection` for that side/bar is rejected rather than
  produced.

#### Scenario: Unreachable take skips the entry

- **WHEN** the initial take price of an entry would be zero or negative
- **THEN** no position is opened for that bar and the execution loop continues,
  while an invalid stop-loss price still fails the run.
