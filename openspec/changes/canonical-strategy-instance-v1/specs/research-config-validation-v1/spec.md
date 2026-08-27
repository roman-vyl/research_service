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
