## MODIFIED Requirements

### Requirement: Distance fill semantics

Research SHALL assume a continuous market. A stop or take level SHALL
fill at exactly the level whenever the bar reached it: for a long
position the stop when `low ≤ level` and the take when `high ≥ level`;
for a short position the stop when `high ≥ level` and the take when
`low ≤ level`. A bar that opens beyond the level SHALL NOT fill at the
open.

#### Scenario: Gap through the stop level

- **WHEN** a long position has a stop at 95 and the bar opens at 90
- **THEN** the fill price SHALL be 95, not the bar open.

#### Scenario: Gap through the take level

- **WHEN** a long position has a take at 108 and the bar opens at 112
- **THEN** the fill price SHALL be 108, not the bar open.

#### Scenario: Short mirror

- **WHEN** a short position has a stop at 105 and a take at 92, and one
  bar opens at 110 while another opens at 88
- **THEN** the stop SHALL fill at 105 and the take at 92.

#### Scenario: Intrabar touch

- **WHEN** the bar open has not crossed the level but the bar's high/low
  range touches it
- **THEN** the fill price is exactly the level.
