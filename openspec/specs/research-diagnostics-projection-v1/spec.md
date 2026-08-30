# Research Diagnostics Projection v1 Specification

## Purpose

Define signal-trace and chart-events BFF projections over immutable,
persisted run bundles, combining Strategy Engine evidence with Research
execution facts at read time.
## Requirements
### Requirement: Immutable-run scope

Research Service SHALL expose signal-trace and chart-events for
immutable new-format runs whose diagnostic artifact has been generated.
A run that exists but has no diagnostic artifact yet SHALL return a
stable "diagnostics not yet generated" response, not an error and not
fabricated/recomputed data.

#### Scenario: Diagnostics for a persisted run

- **WHEN** signal-trace or chart-events is requested for a persisted run
- **AND** that run's diagnostic artifact already exists
- **THEN** the projection is built from that immutable diagnostic
  artifact.

#### Scenario: Diagnostics requested before generation

- **WHEN** signal-trace or chart-events is requested for a persisted run
  that has no diagnostic artifact yet
- **THEN** the response states diagnostics have not been generated for
  this run
- **AND** no upstream call is made to produce them as part of serving
  this request.

### Requirement: Strategy semantics source

The projection SHALL use Strategy Engine component evidence as the
source of strategy semantics, read from the run's separately persisted
diagnostic artifact — never recomputed at read time, and never read
from the mandatory execution-evaluation file (which no longer carries
this data).

#### Scenario: Strategy semantic evidence

- **WHEN** the projection needs a component mask, state value, or
  evidence field
- **THEN** it is read from the run's persisted diagnostic artifact, not
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

### Requirement: Diagnostic-artifact generation is a hard I7 prerequisite

This capability's diagnostic-artifact generation and separate-artifact
read path (already normative above) SHALL be implemented and wired
before, or atomically with, I7's persistence-shape cutover
(`research-run-artifacts-v1`'s "Production persistence shape cutover").
`application/diagnostics/projection.py` SHALL be migrated off reading
`result.strategy_evaluation.component_evidence`/`.raw`/`.entries`/
`.exit_policy` (fields absent from the post-cutover shape) and onto the
generated diagnostic artifact. I7 SHALL NOT ship the persistence cutover
without this migration landing in the same coordinated change — doing
so would leave diagnostics reading fields that no longer exist.

#### Scenario: Diagnostics read from the generated artifact, not the execution file

- **WHEN** diagnostics are requested for a run persisted under the I7
  shape
- **THEN** `application/diagnostics/projection.py` builds its response
  from the separately generated diagnostic artifact
- **AND** it does not access `result.strategy_evaluation` for
  diagnostic content.

