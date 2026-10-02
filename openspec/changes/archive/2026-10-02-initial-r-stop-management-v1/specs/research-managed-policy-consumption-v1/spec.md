## ADDED Requirements

### Requirement: Closed stop execution formula decode

Research SHALL decode projected stop formulas `entry_offset`,
`initial_r_lock`, and `initial_r_trailing`. Omitted `stop_formula` SHALL default
to `entry_offset`. An entry-offset action SHALL reject a trigger reference, and
either initial-R action SHALL require both its action-distance reference and
its trigger-distance reference. Every reference SHALL resolve to an existing
projection distance.

#### Scenario: Legacy action omits formula

- **WHEN** Research decodes a legacy stop action without `stop_formula`
- **THEN** the action SHALL validate and execute as `entry_offset`.

#### Scenario: R action lacks trigger reference

- **WHEN** an initial-R stop action omits its trigger-distance reference
- **THEN** projection decode SHALL fail before execution.

#### Scenario: Dangling trigger reference

- **WHEN** a stop action names a trigger distance absent from the projection
- **THEN** projection decode SHALL fail before execution.

### Requirement: Projection formula is not strategy identity

Research SHALL dispatch stop candidate calculation only on the closed
`stop_formula` execution semantic and opaque distance references. It SHALL NOT
read or require a strategy `component_id` or named raw parameters such as
`trigger_r`, `lock_r`, or `trail_distance_r`.

#### Scenario: Execute opaque initial-R action

- **WHEN** Research receives a valid initial-R stop action
- **THEN** it SHALL calculate the action from formula, referenced distances,
  entry, side, monotonic MFE, and frozen initial risk only.

### Requirement: Execute initial-R lock stop

Research SHALL compare the action's opaque trigger distance with
consumer-local `mfe_r`. Once the trigger and activation phase are met,
`initial_r_lock` SHALL calculate:

- long: `entry_price + action_distance * initial_risk`;
- short: `entry_price - action_distance * initial_risk`.

Initial risk SHALL be the position's entry-to-initial-stop distance frozen at
entry and SHALL never be recomputed from an active managed stop.

#### Scenario: Long and short lock mirror

- **GIVEN** long and short positions entered at 100 with initial risk 2
- **WHEN** their shared projection reaches a 6R trigger with action distance 4
- **THEN** the long candidate SHALL be 108 and the short candidate SHALL be 92.

#### Scenario: Different trades share a projection

- **WHEN** two positions with different frozen risk distances consume the same lock action
- **THEN** each candidate SHALL scale by its own initial risk.

### Requirement: Execute initial-R trailing stop

Once the trigger and activation phase are met, `initial_r_trailing` SHALL
calculate:

- long: `mfe_price - action_distance * initial_risk`;
- short: `mfe_price + action_distance * initial_risk`.

`mfe_price` SHALL be the accumulated favorable extreme: maximum high since
entry for long and minimum low since entry for short. Eager and incremental
consumption SHALL use the same formula and SHALL preserve frozen initial risk
across every state advance.

#### Scenario: Trail follows monotonic MFE

- **WHEN** a two-R trailing action observes MFE of 6R, 7R, 8R, and 11.5R
- **THEN** its candidates SHALL represent 4R, 5R, 6R, and 9.5R of protected profit.

#### Scenario: Retracement does not loosen trail

- **WHEN** price retraces without improving the accumulated favorable extreme
- **THEN** neither eager nor incremental execution SHALL lower a long stop or raise a short stop.

#### Scenario: Eager and incremental parity

- **WHEN** both consumers evaluate the same position, projection, and candles
- **THEN** their phase and effective stop state SHALL match bar for bar.

### Requirement: Initial-R fail-closed behavior

When the position has no initial stop or its frozen initial risk is not
positive, Research SHALL treat `mfe_r` as unavailable and SHALL produce no
candidate for either initial-R stop formula.

#### Scenario: Missing initial protection

- **WHEN** an initial-R action is eligible by phase but the position has no initial stop
- **THEN** no active-stop update SHALL be produced.

### Requirement: Initial-R actions reuse stop ratchet and timing

All candidates SHALL enter the existing side-relative tighten-only arbitration.
A non-tightening candidate SHALL NOT change the active stop or its rule id.
State calculated from bar N SHALL be exposed only at the next executable
candle and managed stop hit detection SHALL remain unchanged.

#### Scenario: Source bar crosses new candidate

- **WHEN** bar N first triggers a trailing candidate and also trades through that level
- **THEN** Research SHALL NOT execute the new stop on bar N.

#### Scenario: Existing stop is tighter

- **WHEN** the effective stop is already more protective than a new R-based candidate
- **THEN** stop price, attribution, and update events SHALL remain unchanged.

#### Scenario: Next candle reaches effective stop

- **WHEN** the stop calculated on bar N is reached by candle N+1
- **THEN** it SHALL enter the existing managed-stop and unified-exit arbitration path.
