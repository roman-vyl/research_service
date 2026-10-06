# research-run-calculation-v1 Specification

## Purpose

Calculate Engine runs for Surface rows without a run as a transaction: materialize, run on the Engine, compare the run's metrics with the row under a fixed tolerance, and publish atomically only when they match.

## Requirements
### Requirement: Calculate plan

`POST /api/research/experiments/{experiment_id}/runs/calculate-plan` SHALL accept
a list of rows addressed by `coords` and SHALL return, per row, whether it is
calculable or skipped with a reason, the `calculable_count` and a `plan_token`.
It SHALL materialize and validate each row and SHALL NOT change any file or start
any Engine run. A row SHALL be skipped as `has_run` when its `run_id` is not empty,
whether or not a run folder exists; only rows with an empty `run_id` SHALL be
calculable. More than 2 000 rows SHALL be rejected with 422
`too_many_rows`. An unknown Experiment SHALL be 404. The Experiment SHALL be
rejected with 409 `materialize_missing`, `unbound_metric`,
`provenance_not_per_row` (provenance is a constant other than `engine`) or
`job_running`.

#### Scenario: Replay row and live run

- **WHEN** a plan is requested for a replay row without a run and a row with a
  live run
- **THEN** the first is calculable and the second is skipped as `has_run`.

#### Scenario: Run id without a run folder

- **WHEN** a plan is requested for a row whose `run_id` is set but whose run
  folder is missing
- **THEN** the row is skipped as `has_run`.

#### Scenario: Engine row whose run was deleted

- **WHEN** a plan is requested for an Engine row with an empty `run_id`
- **THEN** the row is calculable.

### Requirement: Calculate requires the plan token

`POST .../runs/calculate` SHALL accept the same rows and the `plan_token`, SHALL
recompute the token and, if it differs, change nothing and answer 409
`plan_stale`. The token SHALL depend only on the content hash of the result
table, the hash of the `materialize` block and the sorted row keys with their
`config_hash`. Otherwise the service SHALL start a calculation job and answer 202
with its `job_id`. Only one job SHALL run at a time.

#### Scenario: Table changed after the plan

- **WHEN** the result table changes between plan and calculate
- **THEN** the answer is 409 `plan_stale` and no Engine run starts.

### Requirement: Calculation runs through Engine batch

The job SHALL run calculable rows through the existing Research batch path and
Engine `/strategy-evaluations/range-batch`, with at most 1 000 variants per call,
with the Experiment's `research_policy`. When the table declares a market data hash column, rows SHALL
be grouped by it and each group SHALL run only on market data with that hash;
otherwise the group's call SHALL fail before Engine evaluates it.

#### Scenario: Different market data

- **WHEN** the market data available to Engine differ from the row's market data
  hash
- **THEN** the rows of that group end as `engine_failed` and are not published.

### Requirement: Parity gate before publish

The gate SHALL be metric parity only. For each completed row the job SHALL compare every result-binding value of the
Engine run summary with the value stored in the row. Metrics with format
`integer` SHALL be equal. Other metrics SHALL satisfy
`|actual − expected| ≤ max(1e-6 × max(|actual|, |expected|), 1e-9)`. Two empty
values SHALL pass; one empty value SHALL fail. The tolerance SHALL NOT be
configurable. A row with any failing metric SHALL end as `parity_failed` with the
list of `{column, expected, actual}`; its row SHALL NOT change and its run SHALL
be kept and SHALL NOT be written to the row.

#### Scenario: Replay matches Engine

- **WHEN** every metric of the Engine run agrees with the replay row within the
  tolerance
- **THEN** the row is published.

#### Scenario: Replay differs

- **WHEN** the Engine trade count differs from the replay row by one
- **THEN** the row ends as `parity_failed`, keeps its replay metrics, provenance
  and empty `run_id`
- **AND** the journal names the Engine `run_id` and the differing metrics.

### Requirement: Atomic publish

Rows that passed the gate SHALL be published by rewriting the result table
atomically (temporary file in the same folder, then rename) under a per-Experiment
lock that run deletion also takes. Before the first publish of a job the table
SHALL be copied to `runs.pre_calculate_<UTC>.csv`. A published row SHALL get the
Engine value in every result-binding column, the new run id in `run_id_column`,
and `engine` in the provenance column when provenance is a column. No other cell
SHALL change. A row whose cells changed since the plan SHALL NOT be published and
SHALL end as `row_stale`.

#### Scenario: Other cells untouched

- **WHEN** a row is published
- **THEN** all other rows and the row's coordinate cells are byte-identical to the
  backup.

#### Scenario: Row deleted meanwhile

- **WHEN** a run deletion changed the row between plan and publish
- **THEN** the row ends as `row_stale` and the Engine run is kept as diagnostic.

### Requirement: Calculated is derived

Research Service SHALL NOT store a calculation status in the result table. A row
SHALL count as calculated when its provenance is `engine` and its `run_id` is not
empty.

#### Scenario: Published row

- **WHEN** a replay row is published
- **THEN** the results route returns it with provenance `engine` and the new
  `run_id`, and no other status field.

### Requirement: Job status, cancel and journal

`GET .../calculations/{job_id}` SHALL return the job state (`running`,
`completed`, `cancelled`, `failed`), counts per outcome and per-row outcomes
(`published`, `parity_failed`, `engine_failed`, `row_stale`, `cancelled`) with
`run_id` and parity differences when present. `POST .../calculations/{job_id}/cancel`
SHALL stop the job before its next batch call; rows already published SHALL stay
published. Each row outcome SHALL be appended to `runs_calculated.jsonl` in the
Experiment folder with job id, row key, `config_hash`, outcome, `run_id`,
parity differences and UTC time. An unknown job SHALL be 404.

#### Scenario: Cancel mid-job

- **WHEN** a job is cancelled after its first batch call was published
- **THEN** the first call's rows stay published and the remaining rows end as
  `cancelled` without Engine runs.

