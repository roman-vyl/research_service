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
`|actual − expected| ≤ max(abs_tolerance, 1e-3 × max(|actual|, |expected|))`, where
`abs_tolerance` is fixed per Engine summary field (the last segment of the
result-binding path): `return_pct`, `win_rate`, `max_drawdown`, `profit_factor` 1e-4;
`cumulative_net_r` 0.01; `net_pnl` 1.0; any other field 1e-9. Two empty
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

#### Scenario: Stored value rounded

- **WHEN** the row stores cumulative R `5.34` and the Engine returns `5.34421`
- **THEN** that metric passes.

#### Scenario: Near zero

- **WHEN** the row stores return `0.0` and the Engine returns `0.00004`
- **THEN** that metric passes; with `0.0002` the row ends as `parity_failed`.

#### Scenario: Result changed

- **WHEN** the row stores return `0.8861` and the Engine returns `0.8880`
- **THEN** the row ends as `parity_failed`.

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

### Requirement: Rows with an option off are calculable

A row whose option cell is empty SHALL be planned and calculated like any
other row, and the result row SHALL keep its empty option cell. The plan SHALL list
`option_inconsistent` among its skip reasons.

#### Scenario: Both kinds on one Surface

- **WHEN** a plan is requested for a row with a break-even trigger and a row
  without one, both without a run
- **THEN** both are calculable and the rows keep their option cells after publish.

### Requirement: Calculate may create a row from coordinates

When the coordinates of a requested row match no row of the table and every
column bound by the `materialize` block (main bindings and bindings of the
options that are on) is a dimension column whose value the coordinates carry,
the plan SHALL list the row as calculable with `new_row: true` instead of
`row_not_found`. Materialize SHALL read those values from the coordinates (for a
grid dimension, the value in the requested grid). A row whose bound columns
cannot all be read from the coordinates SHALL be skipped as `row_not_creatable`
with the missing columns. A calculated new row SHALL be appended to the table
with the dimension columns from the coordinates, the metrics, `run_id` and
provenance `engine` from the Engine run and every other column empty; there is no
stored row to compare, so the parity gate is not applied to it. `plan_token`
SHALL cover the coordinates of new rows. A row that already exists keeps its
rules (`has_run`, `ambiguous_row`).

#### Scenario: Break-even on a Surface without break-even runs

- **WHEN** the plan is requested for a cell with the break-even option on whose
  coordinates have no row
- **THEN** the row is calculable with `new_row: true`, and after Calculate the
  table holds one new row with the run and the metrics.

#### Scenario: Bound column not in the coordinates

- **WHEN** a bound column is derived and not a dimension column
- **THEN** the row is skipped as `row_not_creatable`.

### Requirement: Optional dimension declares its values

A result-schema dimension with `optional: true` MAY declare `values`, the numbers
the option can take; the workbench SHALL offer them when no row carries a value, so a
cell that has no run can still be addressed.

#### Scenario: No row has a value yet

- **WHEN** the table has no row with a break-even trigger and the dimension
  declares `values`
- **THEN** the workbench offers those values and the plan accepts them as
  coordinates.

#### Scenario: Value outside the declared values

- **WHEN** an optional dimension declares `values` and a requested row carries a
  value that is not among them
- **THEN** the row is skipped as `coord_not_allowed`.

