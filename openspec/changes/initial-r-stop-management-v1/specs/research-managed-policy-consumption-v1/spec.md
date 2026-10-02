## ADDED Requirements

### Requirement: R-based stop actions

Research SHALL accept an optional `stop_basis: "lock_r" | "trail_r"` on
a `stop_action` rule and SHALL compute that rule's candidate stop on
each bar as:

- no `stop_basis`: `reference_entry_price ± distance` (unchanged);
- `lock_r`: `reference_entry_price ± distance × initial_risk`;
- `trail_r`: `mfe_price ∓ distance × initial_risk`;

with `+` toward profit for the entry form and `∓` away from the best
price for the trail form, by side. `initial_risk` SHALL be the frozen
value `mfe_r` uses, and `mfe_price` the best price from the entry bar
through the current bar.

- An R-based candidate SHALL be discarded when the position has no
  initial stop or a non-positive initial risk, and when it is not
  tighter than the initial stop.
- The candidate SHALL join the existing tightest-candidate ratchet; the
  active stop SHALL never move away from the market.
- Dispatch SHALL be on `stop_basis`; Research SHALL NOT read a
  component id.
- The eager timeline builder and the incremental advance SHALL produce
  the same active stop on every bar.

#### Scenario: Trail in initial R

- **GIVEN** a long position entered at 100 with initial stop 98 and a
  `trail_r` rule with distance 2, active
- **WHEN** the best price reaches 112, then 114, then price falls to 110
- **THEN** the active stop SHALL be 108, then 110, and SHALL stay 110
- **AND** the short mirror (entry 100, stop 102) SHALL give 92, 90, 90.

#### Scenario: Lock in initial R

- **GIVEN** the same long position and a `lock_r` rule with distance 4
- **WHEN** the rule becomes active
- **THEN** the active stop SHALL be 108 from the next bar.

#### Scenario: Not tighter than the initial stop

- **GIVEN** a `trail_r` rule with distance 2 active from entry
- **WHEN** the best price is 100.5 (MFE 0.25R, stop_R −1.75)
- **THEN** the rule SHALL propose no candidate.

#### Scenario: No basis unchanged

- **WHEN** a projection has no `stop_basis` on any rule
- **THEN** managed timelines and trades SHALL equal those before this
  change.
