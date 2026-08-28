## MODIFIED Requirements

### Requirement: Immutable-run scope

Research Service SHALL expose signal-trace and chart-events for
immutable new-format runs whose diagnostic artifact has been generated.
A run that exists but has no diagnostic artifact yet SHALL return a
stable "diagnostics not yet generated" response, not an error and not
fabricated/recomputed data.

#### Scenario: Diagnostics for a persisted run with a diagnostic artifact

- **WHEN** signal-trace or chart-events is requested for a persisted run
  that already has a diagnostic artifact
- **THEN** the projection is built from that artifact.

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

## ADDED Requirements

### Requirement: Diagnostic-artifact generation is a distinct write operation

Generating a run's diagnostic artifact SHALL be a separate, explicit
operation from reading a diagnostics projection. Generation MAY call
Strategy Engine (for the same immutable strategy and
`market_data_hash`/range the run was originally evaluated against);
reading an already-generated artifact SHALL NOT.

#### Scenario: Generation is idempotent per run

- **WHEN** diagnostics generation is requested for a run that already
  has a diagnostic artifact
- **THEN** the existing artifact is not silently recomputed and
  replaced without an explicit regeneration request.

#### Scenario: No read-time upstream calls, still

- **WHEN** a signal-trace or chart-events route is served
- **THEN** no HTTP call is made to Market Data Service or Strategy
  Engine while building that response — this requirement is unchanged
  by diagnostics becoming optional; it governs the read path, not the
  separate generation operation above.

### Requirement: Diagnostic generation ownership and provenance fail-closed

Research Service SHALL own requesting and persisting diagnostics.
Strategy Engine SHALL own computing them. A generation request SHALL use
the target run's own already-stored provenance
(`market_data_hash`/range/`config_hash`) to call Strategy Engine's
diagnostic-evaluation entrypoint — never a freshly re-derived value.
Research Service SHALL reject and refuse to persist a diagnostic
response whose `config_hash`, `market_data_hash`, or `bar_count` does
not exactly match the target run's stored provenance.

#### Scenario: Diagnostic response provenance matches the run

- **WHEN** a diagnostic-evaluation response is received for a
  generation request
- **THEN** it is persisted as that run's diagnostic artifact only if its
  `config_hash`, `market_data_hash`, and `bar_count` exactly match the
  run's own stored execution-evaluation provenance.

#### Scenario: Provenance mismatch is rejected, not silently accepted

- **WHEN** a diagnostic-evaluation response's provenance does not match
  the target run's stored provenance
- **THEN** Research Service SHALL reject the response and SHALL NOT
  persist it as that run's diagnostic artifact.
