## MODIFIED Requirements

### Requirement: Candidate validity

A batch MUST contain at least one candidate and unique `candidate_id`
values. `run_id` SHALL NOT be part of a batch candidate request and SHALL
NOT be used for pre-execution uniqueness validation — it does not exist
until a candidate has run, since `run_id` is Research-generated per
`research-backtest-api-v1`.

#### Scenario: Duplicate candidate identity

- **WHEN** a batch request contains two candidates with the same
  `candidate_id`
- **THEN** the batch is rejected before any candidate executes.

## ADDED Requirements

### Requirement: Result correlation by candidate_id

Batch candidate results SHALL correlate to their originating request
solely via `candidate_id`. `run_id` SHALL NOT be used as a pre-execution
or cross-request correlation key.

#### Scenario: Matching a result to its request

- **WHEN** a batch summary is inspected
- **THEN** each `BatchCandidateResult` is matched back to its originating
  candidate via `candidate_id`, not via any run identity.

### Requirement: Run identity generated only on success

A successful candidate's result SHALL include the Research-generated
`run_id` for the run that candidate produced. A failed candidate SHALL
NOT report a `run_id`, since no run was created.

#### Scenario: Successful candidate reports generated run_id

- **WHEN** a candidate completes successfully
- **THEN** its result includes the `run_id` Research Service generated
  for that run.

#### Scenario: Failed candidate has no run_id

- **WHEN** a candidate fails before a run is created
- **THEN** its result reports no `run_id`.

### Requirement: One candidate is one canonical strategy instance

Each batch candidate SHALL wrap exactly one canonical strategy-instance
identity subset (`canonical-strategy-instance-v1`), the same shape a
single, non-batched backtest request uses. Batch execution SHALL NOT
introduce a second strategy-instance representation or a
multiple-instances-per-candidate shape.

#### Scenario: Candidate strategy shape matches single-instance backtest

- **WHEN** a batch candidate's strategy input is inspected
- **THEN** it has the same identity-subset shape
  (`strategy_id`/`ticker`/`base_timeframe`/`raw_spec`) as a standalone
  `POST /api/research/backtests` request, with no `enabled`, `family`,
  `variant`, `strategy_version`, or caller-supplied `instance_id`/`run_id`.
