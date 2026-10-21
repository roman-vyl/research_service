# Research Config Validation v1 Specification

## Purpose

Define the preserved Workbench config-validation route, which delegates
strategy-instance semantics to Strategy Engine while validating only the
research/execution envelope locally.
## Requirements
### Requirement: Preserved Workbench DTO

`POST /api/research/config/validate` SHALL preserve the Workbench response
DTO.

#### Scenario: Validation response shape

- **WHEN** a client calls `POST /api/research/config/validate`
- **THEN** the response uses the existing Workbench validation-result DTO.

### Requirement: Local envelope validation only

Research Service SHALL validate only research/execution envelope semantics
locally.

#### Scenario: Envelope-level error

- **WHEN** the research/execution envelope of a draft is malformed
- **THEN** Research Service reports that error itself, without calling
  Strategy Engine.

### Requirement: Delegated strategy semantics

Strategy instance semantics SHALL be delegated to Strategy Engine.

#### Scenario: Strategy instance validation

- **WHEN** the envelope is well-formed and a strategy instance needs
  semantic validation
- **THEN** Research Service delegates that check to Strategy Engine rather
  than validating strategy semantics itself.

### Requirement: Stable upstream error paths

Upstream validation errors SHALL retain stable paths and messages.

#### Scenario: Strategy Engine reports an invalid instance

- **WHEN** Strategy Engine returns a validation error for a strategy
  instance
- **THEN** the error's field path and message are passed through unchanged
  to the Workbench response.

### Requirement: Deployable instance shape per draft entry

Each entry in a config draft's `instances` collection SHALL be validated
as one deployable strategy instance (`canonical-strategy-instance-v1`):
`enabled`, `strategy_id`, `ticker`, `base_timeframe`, `raw_spec`. The
draft's envelope-level fields (Research grouping only, such as
`experiment_id`) SHALL NOT be treated as part of any individual
instance's identity, and an instance's `enabled` value SHALL NOT affect
whether it validates successfully.

#### Scenario: Instance missing strategy_id rejected

- **WHEN** a draft's `instances` entry has no `strategy_id`
- **THEN** validation reports an error for that instance and the draft is
  rejected.

#### Scenario: Legacy identity field on an instance rejected

- **WHEN** a draft's `instances` entry carries `variant`, `family`,
  `strategy_version`, or an explicit `instance_id`
- **THEN** validation reports an error for that instance and the draft is
  rejected.

#### Scenario: Disabled instance validates normally

- **WHEN** a draft's `instances` entry has `enabled=false` and an
  otherwise well-formed identity subset
- **THEN** validation succeeds for that instance.

### Requirement: One strategy type per experiment/config

`draft.strategy_id` SHALL identify the single strategy type an
experiment/config explores. Every entry in `draft.instances` SHALL have a
`strategy_id` equal to `draft.strategy_id`. An experiment/config SHALL
NOT mix candidate instances of different strategy types.

#### Scenario: Matching instance strategy_id accepted

- **WHEN** every entry in `draft.instances` has `strategy_id` equal to
  `draft.strategy_id`
- **THEN** this invariant does not reject the draft.

#### Scenario: Mismatching instance strategy_id rejected

- **WHEN** a draft's `instances` entry has a `strategy_id` different
  from `draft.strategy_id`
- **THEN** validation reports an error identifying that instance by
  index and the draft is rejected before any Strategy Engine delegation.

