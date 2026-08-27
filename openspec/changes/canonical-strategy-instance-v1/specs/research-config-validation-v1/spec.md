## ADDED Requirements

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
