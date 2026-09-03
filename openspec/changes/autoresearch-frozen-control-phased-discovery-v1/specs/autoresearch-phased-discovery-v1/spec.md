## Purpose

Defines the causal, six-stage AutoResearch discovery program for one strategy family: a frozen
naked control, independent structural-entry discovery, structural-region shortlisting, and
symmetric exit-geometry measurement over that shortlist -- so exit distance is never scanned
alongside structural entry evidence in the same stage.

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

### Requirement: Structural discovery shortlists regions, not a single winner

The `entry_region_selection` stage SHALL accept one to three structurally supported width×lookback
regions carried forward from `structural_interaction`, each independently satisfying the existing
structural-promise evidence bar (stability, neighborhood support, adequate sample, no
disqualifying thinning or concentration). It SHALL NOT require or assume a single best region.

#### Scenario: Two independently robust regions both shortlist

- **WHEN** `structural_interaction` finds two non-overlapping width×lookback regions that each
  independently show stable, neighborhood-supported structural promise
- **THEN** both SHALL be eligible to shortlist into `entry_region_selection` rather than only the
  higher-scoring one

#### Scenario: An unsupported spike does not shortlist

- **WHEN** a candidate region shows a favorable point result without neighborhood support or
  adequate sample
- **THEN** it SHALL NOT be shortlisted into `entry_region_selection`

### Requirement: Exit geometry scans symmetric distance only over the shortlist

The `exit_geometry` stage SHALL scan symmetric ATR exit distance only across the region(s)
shortlisted by `entry_region_selection`. It SHALL NOT re-open the width or lookback search space,
and SHALL NOT scan exit distance against the full original Phase B parameter space.

#### Scenario: Exit-geometry sweep stays inside the shortlisted region

- **WHEN** `exit_geometry` constructs its distance sweep for a shortlisted region
- **THEN** every candidate SHALL hold that region's width and lookback fixed and SHALL vary only
  exit distance

#### Scenario: Exit-geometry cannot be entered before a region is shortlisted

- **WHEN** no region has been accepted out of `entry_region_selection` for the active strategy
- **THEN** a next step that schedules `exit_geometry` SHALL hard-stop as a causal-order violation

### Requirement: Frozen-dimension reference identity extends to exit-geometry distances

The harness-owned "reference identity a worker must echo, not compute" mechanism (published
per-value reference hashes, deterministic supervisor recomputation) SHALL apply to every symmetric
exit distance value a session measures against a fixed strategy: the single Phase A control value,
and each configured distance swept in `exit_geometry` for a given shortlisted region. `structural_entry`/
`structural_interaction` (width, lookback) remain continuous, worker-proposed dimensions with no
fixed configured value set, exactly as today, and this requirement does not extend the reference-hash
mechanism to them.

#### Scenario: Exit-geometry distance reference identity is published, not computed by the worker

- **WHEN** a planning worker constructs an `exit_geometry` batch candidate for a configured distance
  value over a shortlisted region
- **THEN** the session state SHALL publish the canonical reference hash for that (region, distance)
  pair the same way it publishes per-geometry reference hashes today, and the worker SHALL copy it
  rather than execute code to derive it

### Requirement: Managed/dynamic exit logic remains out of scope

No stage introduced by this capability SHALL enable `exit_management.mode: "managed"` or any
bar-to-bar managed exit logic. A future managed-exit stage is anticipated but not specified here.

#### Scenario: Exit-geometry candidates stay non-managed

- **WHEN** `exit_geometry` constructs a batch candidate
- **THEN** the candidate's `exit_management` SHALL remain unset/naked and `managed_policy_enabled`
  SHALL be derived as `false` by the existing harness-owned derivation
