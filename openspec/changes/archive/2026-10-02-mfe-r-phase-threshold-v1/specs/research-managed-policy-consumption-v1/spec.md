## ADDED Requirements

### Requirement: Trade metric `mfe_r`

Research SHALL support `trade_metric: "mfe_r"` in the managed projection,
for atomic phase rules, composite thresholds and `at_least` terms. The
metric SHALL be

`|mfe_price - reference_entry_price| / initial_risk`

compared with `>=` against the projection's distance series, where
`initial_risk = |reference_entry_price - initial stop level|` is taken
from the position's initial protection at entry.

- `initial_risk` SHALL be frozen at entry and SHALL be the same value on
  every bar of the trade, in the eager timeline builder and in the
  incremental advance (it SHALL be carried through every state
  transition, not recomputed from a moved stop).
- A position with no initial stop, or with a non-positive initial risk,
  SHALL never meet an `mfe_r` threshold.
- Dispatch SHALL remain on `trade_metric`; Research SHALL NOT read a
  component id.

#### Scenario: Threshold in multiples of initial risk

- **GIVEN** a long position entered at 100 with initial stop 98 and an
  `mfe_r` threshold of 3
- **WHEN** the best price reaches 106
- **THEN** the phase rule SHALL fire on that bar
- **AND** the short mirror (entry 100, stop 102, best 94) SHALL fire on
  the same bar index.

#### Scenario: Initial risk survives state advance

- **WHEN** the incremental advance steps a trade through bars
- **THEN** its phases SHALL equal the eager timeline's phases bar for
  bar.

#### Scenario: No initial stop

- **WHEN** the position has no initial stop
- **THEN** an `mfe_r` rule SHALL never fire.
