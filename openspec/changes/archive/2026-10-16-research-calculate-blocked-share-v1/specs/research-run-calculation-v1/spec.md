## ADDED Requirements

### Requirement: Blocked share from a base run

For every calculated row, Calculate SHALL also run the row's base spec: the materialized template with the row's
bindings and no option item. Rows with the same base spec SHALL share one base run, in the same Engine batch call as
the rows. The row's summary SHALL then carry `blocked_share = 1 - entry_signal_count(row) /
entry_signal_count(base)`, 0 when the base has no entry signal, and a result binding `"blocked_share":
"blocked_share"` SHALL read it. A row whose base run failed SHALL settle as `engine_failed` and SHALL NOT be
published. Base runs SHALL NOT be linked to a row and SHALL be listed in the job journal. The parity tolerance of
`blocked_share` SHALL be an absolute 1e-4.

#### Scenario: Many rows, one base

- **WHEN** a Calculate has eight rows that differ only in their option cells
- **THEN** the batch call has eight row candidates and one base candidate.

#### Scenario: Share of the blocked signals

- **WHEN** a row's run has 345 entry signals and its base run 1275
- **THEN** the row's `blocked_share` is 1 - 345 / 1275.

#### Scenario: Row with every option off

- **WHEN** a row has every option off
- **THEN** its base spec equals its spec and its `blocked_share` is 0.
