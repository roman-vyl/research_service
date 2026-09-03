## Purpose

Defines the causal AutoResearch discovery program for one strategy family: a frozen naked control,
then two independent structural-entry discovery branches (width, lookback) that each start fresh
from that control, then their interaction -- so exit distance is never scanned alongside structural
entry evidence, and width discovery is never implicitly conditioned on a lookback choice or vice
versa. Downstream region-shortlisting and exit-geometry stages are reserved by name only until real
B1/B2/B3 evidence shows what shape they should take.

## ADDED Requirements

### Requirement: Phase A freezes exit geometry as a single control, not a scan

The `descriptive_baseline` stage SHALL measure exactly one pre-configured, operator-approved
symmetric ATR exit distance against the naked starting strategy. It SHALL NOT expose
`symmetric_measurement_geometry` (or any other exit-distance dimension) as a scannable stage
dimension, and the stage contract SHALL NOT accept more than one measured value for this stage
across a session.

#### Scenario: Naked control uses one frozen exit distance

- **WHEN** a session initializes its `descriptive_baseline` stage
- **THEN** the frozen starting strategy's exit distance is fixed at session creation and every
  `descriptive_baseline` batch candidate SHALL use that identical value

#### Scenario: A second Phase A exit distance is rejected

- **WHEN** a planning worker constructs a `descriptive_baseline` batch request with an exit
  distance different from the frozen control value
- **THEN** the stage contract SHALL reject the request

### Requirement: Structural discovery stages run under the frozen control exit only

`structural_entry` and `structural_interaction` stages (width, lookback, and width×lookback
discovery) SHALL hold the symmetric exit distance fixed at the Phase A control value for every
candidate. Exit distance SHALL NOT be an available semantic dimension in these stages.

#### Scenario: Width discovery does not vary exit distance

- **WHEN** a `structural_entry` (width) batch candidate is constructed
- **THEN** its exit distance SHALL equal the frozen Phase A control value and only the width
  dimension SHALL vary from the naked baseline

#### Scenario: Lookback discovery starts from the naked baseline, not the width winner

- **WHEN** a `structural_entry` (lookback) batch candidate is constructed
- **THEN** it SHALL vary only the lookback dimension from the naked baseline and SHALL NOT carry
  forward any width value chosen by prior width discovery

### Requirement: Width and lookback discovery are independent branches off the control

B1 (width) and B2 (lookback) SHALL each depend only on the closed `descriptive_baseline` control
reference. Neither SHALL be a prerequisite of the other: B2 SHALL be reachable whether or not B1 has
been run or closed, and B1 SHALL be reachable whether or not B2 has been run or closed. Only B3
(width×lookback interaction) SHALL require both B1 and B2 durably closed. Running B1 before B2 (or
the reverse) in a given session is process serialization by a single-worker-at-a-time harness, never
a causal dependency the stage contract enforces.

#### Scenario: Lookback discovery is reachable before width discovery is closed

- **WHEN** a session's `descriptive_baseline` control reference is closed and no `structural_entry`
  (width) disposition has been recorded yet
- **THEN** a plan targeting `structural_entry` (lookback) SHALL still be accepted

#### Scenario: Width discovery is reachable before lookback discovery is closed

- **WHEN** a session's `descriptive_baseline` control reference is closed and no `structural_entry`
  (lookback) disposition has been recorded yet
- **THEN** a plan targeting `structural_entry` (width) SHALL still be accepted

#### Scenario: Interaction discovery requires both branches closed

- **WHEN** a plan targets `structural_interaction` (width×lookback)
- **THEN** the stage contract SHALL require both the width and the lookback `structural_entry`
  dispositions to already be durably closed (`characterized` or `terminally_rejected`)

### Requirement: Downstream region-selection and exit-geometry stages are reserved, not defined

`entry_region_selection` and `exit_geometry` exist as reserved stage names and phase bindings only.
Their behavioral contract -- what a "result" of B1/B2/B3 durably looks like, how B3 evidence is
carried into a shortlist, the shortlist acceptance rule, and any per-region reference-identity
mechanism for a later symmetric-exit sweep -- is deliberately undefined until a HOST research run
produces real B1/B2/B3 evidence to design against. No execution plan SHALL target either stage; the
harness SHALL fail closed rather than accept an undefined contract, and no stage transition SHALL
ever set the active stage to either of them automatically.

#### Scenario: A plan cannot target entry_region_selection

- **WHEN** a planning worker constructs a plan whose `stage_context.active_stage` is
  `entry_region_selection`
- **THEN** the harness SHALL reject it because that stage's execution semantics are not yet defined

#### Scenario: A plan cannot target exit_geometry

- **WHEN** a planning worker constructs a plan whose `stage_context.active_stage` is `exit_geometry`
- **THEN** the harness SHALL reject it because that stage's execution semantics are not yet defined

#### Scenario: Closing B3 does not auto-advance into entry_region_selection

- **WHEN** the `structural_interaction` (B3) disposition closes (`characterized` or
  `terminally_rejected`)
- **THEN** the session's active stage SHALL remain `structural_interaction`; a worker that proposes
  no further experiment reaches ordinary terminal completion, not a transition into
  `entry_region_selection`

### Requirement: Managed/dynamic exit logic remains out of scope

No stage introduced or reserved by this capability SHALL enable `exit_management.mode: "managed"` or
any bar-to-bar managed exit logic. A future managed-exit stage is anticipated but not specified here.

#### Scenario: Batch candidates stay non-managed

- **WHEN** any stage in this capability constructs a batch candidate
- **THEN** the candidate's `exit_management` SHALL remain unset/naked and `managed_policy_enabled`
  SHALL be derived as `false` by the existing harness-owned derivation
