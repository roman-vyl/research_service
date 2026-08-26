# Research Managed Policy Consumption v1 Specification

## Purpose

Define how Research Service consumes Strategy Engine's managed-replay
policy artifacts into execution candidates.

## Requirements

### Requirement: Policy ownership

Research Service MUST consume managed policy artifacts from Strategy Engine
(ownership boundary: `research-service-boundaries-v1`).

#### Scenario: Managed candidate source

- **WHEN** a managed exit candidate is built for an open position
- **THEN** its phase, stop, and take-profile values come from a Strategy
  Engine managed-replay artifact, never a locally recomputed policy.

### Requirement: Effective timing

A managed decision created at the end of bar N MUST NOT be executable on
bar N and MUST become effective only at `effective_from_time_ms`.

#### Scenario: Decision effective on a later bar

- **WHEN** a managed decision's `effective_from_time_ms` is the open time of
  bar N+1
- **THEN** that decision is not used for arbitration on bar N.

### Requirement: Managed stop execution

A managed stop crossed at bar open MUST fill at the open. An intrabar touch
MUST fill at the stop level.

#### Scenario: Managed stop gapped through at open

- **WHEN** the bar open price is already beyond the current managed stop
- **THEN** the managed-stop candidate fills at the open, not the stop
  level.

### Requirement: Runtime exits

Runtime exit rules active for the inherited bar MUST become close-price
candidates with the legacy candidate class derived from `exit_kind`.

#### Scenario: Runtime exit rule active

- **WHEN** a runtime exit rule is active for the bar under the inherited
  managed state
- **THEN** a close-price candidate is created whose candidate class is
  derived from that rule's `exit_kind`.

### Requirement: Attribution

Rule IDs, component IDs, and exit kinds available in Strategy Engine events
MUST be preserved on Research execution candidates.

#### Scenario: Candidate attribution

- **WHEN** a managed candidate is built from a Strategy Engine event that
  carries a rule ID, component ID, or exit kind
- **THEN** those identifiers are copied onto the Research execution
  candidate unchanged.
