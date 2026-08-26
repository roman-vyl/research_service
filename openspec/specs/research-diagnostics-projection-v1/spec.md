# Research Diagnostics Projection v1 Specification

## Purpose

Define signal-trace and chart-events BFF projections over immutable,
persisted run bundles, combining Strategy Engine evidence with Research
execution facts at read time.

## Requirements

### Requirement: Immutable-run scope

Research Service SHALL expose signal-trace and chart-events for immutable
new-format runs.

#### Scenario: Diagnostics for a persisted run

- **WHEN** signal-trace or chart-events is requested for a persisted run
- **THEN** the projection is built from that run's immutable bundle.

### Requirement: Strategy semantics source

The projection SHALL use Strategy Engine component evidence as the source
of strategy semantics.

#### Scenario: Strategy semantic evidence

- **WHEN** the projection needs a component mask, state value, or evidence
  field
- **THEN** it is read from the persisted Strategy Engine evaluation, not
  recomputed.

### Requirement: Execution facts source

The projection SHALL use Research execution events as the source of fill
and lifecycle facts.

#### Scenario: Fill/lifecycle evidence

- **WHEN** the projection needs a fill price, event, or lifecycle
  transition
- **THEN** it is read from the persisted Research execution events.

### Requirement: No read-time upstream calls

The projection SHALL NOT call Market Data Service or Strategy Engine at
read time.

#### Scenario: Serving a diagnostics request

- **WHEN** a diagnostics route is called
- **THEN** no HTTP call is made to Market Data Service or Strategy Engine
  while building the response.

### Requirement: Grid-aligned dense arrays

Dense arrays SHALL remain aligned to the requested market-grid slice.

#### Scenario: Windowed diagnostics request

- **WHEN** a diagnostics request slices a window of the run
- **THEN** every dense array in the response is aligned to that same
  market-grid slice.

### Requirement: Portfolio entry derivation

`portfolio_entry` SHALL equal strategy entry gated by `stop_ready`.

#### Scenario: Entry true but stop not ready

- **WHEN** Strategy Engine's entry decision is true but `stop_ready` is
  false on the same bar
- **THEN** `portfolio_entry` for that bar is false.

### Requirement: Stable errors on unknown references

Unknown single-run variants and context overlay references SHALL return
stable invalid-request errors.

#### Scenario: Unknown context overlay

- **WHEN** a request names a context overlay that does not exist for the
  run
- **THEN** the response is a stable `invalid_request` error.
