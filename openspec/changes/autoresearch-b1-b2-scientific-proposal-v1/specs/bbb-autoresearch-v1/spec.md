## MODIFIED Requirements

### Requirement: Fresh worker per iteration

The supervisor SHALL launch a fresh process for exactly one iteration, validate its structured
result after exit, and launch another fresh process only when continuation is valid. For the
`A_CONTROL` stage, the supervisor SHALL deterministically materialize that iteration's
`execution_plan.json` from frozen session and stage-contract state instead of launching a planning
worker process; the iteration's first worker process is its interpretation call. For `B1_WIDTH` and
`B2_LOOKBACK`, the supervisor SHALL deterministically materialize that stage's first iteration
`execution_plan.json` from the session's `stage_initial_sweeps` and frozen stage-contract state
instead of launching a planning worker process, where "first iteration" means no prior iteration at
that stage has committed (recorded in `state["stage_history"]`); every subsequent iteration at that
stage SHALL launch a fresh planning worker process with full freedom over candidate values,
unconstrained by `stage_initial_sweeps`, and once a stage has one committed iteration,
`stage_initial_sweeps` SHALL NOT be used again for that stage in that session, including as a
fallback after a later planning failure. Every other stage, and interpretation for every stage
including `A_CONTROL`, `B1_WIDTH`, and `B2_LOOKBACK`, SHALL continue to run as a fresh worker process
per this requirement unchanged.

#### Scenario: Autonomous continuation

- **WHEN** iteration N completes with a proposed next experiment
- **THEN** state advances atomically and a fresh process receives iteration N+1.

#### Scenario: A_CONTROL requires no planning worker

- **WHEN** the active stage for an iteration is `A_CONTROL`
- **THEN** the supervisor materializes that iteration's `execution_plan.json` deterministically from
  frozen session and stage-contract state and does not launch a planning worker process for it.

#### Scenario: A_CONTROL interpretation still runs as a fresh worker

- **WHEN** the `A_CONTROL` iteration's canonical execution completes
- **THEN** the supervisor launches a fresh worker process for interpretation of that result, and that
  worker reports the semantic fields (hypothesis, question, competing explanation, proposed next
  experiment) required of interpretation for every stage.

#### Scenario: B1_WIDTH or B2_LOOKBACK first entry requires no planning worker

- **WHEN** the active stage for an iteration is `B1_WIDTH` or `B2_LOOKBACK` and `state["stage_history"]`
  contains no prior committed entry at that stage
- **THEN** the supervisor materializes that iteration's `execution_plan.json` deterministically from
  `state["stage_initial_sweeps"]` for that stage and the frozen `stage_contract` semantic binding, and
  does not launch a planning worker process for it.

#### Scenario: B1_WIDTH or B2_LOOKBACK subsequent entry restores full worker freedom

- **WHEN** the active stage for an iteration is `B1_WIDTH` or `B2_LOOKBACK` and `state["stage_history"]`
  already contains a prior committed entry at that stage
- **THEN** the supervisor launches a fresh planning worker process free to choose any candidate
  values for that stage's bound dimension, unconstrained by `state["stage_initial_sweeps"]`.

#### Scenario: Initial sweep is never a fallback after first commit

- **WHEN** a stage has one committed iteration and a later planning worker process for that stage
  fails
- **THEN** the supervisor retries the planning worker process and SHALL NOT materialize a plan from
  `state["stage_initial_sweeps"]` for that stage again.
