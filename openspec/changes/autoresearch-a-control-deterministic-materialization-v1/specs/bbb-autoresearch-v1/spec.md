## MODIFIED Requirements

### Requirement: Fresh worker per iteration

The supervisor SHALL launch a fresh process for exactly one iteration, validate its structured
result after exit, and launch another fresh process only when continuation is valid. For the
`A_CONTROL` stage, the supervisor SHALL deterministically materialize that iteration's
`execution_plan.json` from frozen session and stage-contract state instead of launching a planning
worker process; the iteration's first worker process is its interpretation call. Every other stage,
and interpretation for every stage including `A_CONTROL`, SHALL continue to run as a fresh worker
process per this requirement unchanged.

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
