## MODIFIED Requirements

### Requirement: Managed stop execution

A managed stop MUST fill at exactly its current level whenever the bar
reached it (`low ≤ level` for long, `high ≥ level` for short), under the
same continuous-market model as the initial stop. A bar that opens
beyond the managed stop MUST NOT fill at the open.

#### Scenario: Managed stop gapped through at open

- **WHEN** the bar open price is already beyond the current managed stop
- **THEN** the managed-stop candidate fills at the stop level, not the
  open.

#### Scenario: Managed stop intrabar touch

- **WHEN** the bar open has not crossed the managed stop but the bar's
  range touches it
- **THEN** the managed-stop candidate fills at the stop level.
