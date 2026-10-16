## ADDED Requirements

### Requirement: Period split in the research policy

The `research_policy` of a materialize block MAY carry `period_split_ms`, a non-negative integer. Calculate SHALL
pass it to the batch request; without it the batch default applies. Result bindings MAY name the period, yearly and
trade-average fields of the batch summary, a yearly field as `years.<year>.return_pct`.

#### Scenario: Custom split

- **WHEN** a manifest's research policy sets `period_split_ms` to 2024-01-01T00:00:00Z
- **THEN** the calculated rows' `is_net_pnl` and `oos_net_pnl` are split at that instant.

#### Scenario: Bound year return of a year without trades

- **WHEN** a row binds `return_2021` to `years.2021.return_pct` and the run has no 2021 trade
- **THEN** the value is null, and the row passes parity only when its stored cell is empty.
