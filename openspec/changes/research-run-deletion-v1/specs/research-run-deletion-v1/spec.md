## ADDED Requirements

### Requirement: A point has a run or it does not

A result row SHALL have a full Engine run if and only if its `run_id` cell is not
empty and the run folder exists at `<artifacts_root>/<run_id>/`. A row without a
run SHALL keep all of its parameters, metrics and provenance. There SHALL be no
partial or "pruned" run state.

#### Scenario: Deleted run

- **WHEN** a run is deleted
- **THEN** its row still returns the same dimension and metric values from the
  results route
- **AND** the row's `run_id` is empty.

### Requirement: Delete plan

`POST /api/research/experiments/{experiment_id}/runs/delete-plan` SHALL accept a
list of `run_id` and SHALL return `run_count`, `file_count`, `bytes`,
`already_absent`, the `skipped` list with a reason for each skipped id, and a
`plan_token`. It SHALL NOT change any file. A `run_id` SHALL be skipped as
`invalid_run_id` when it does not match `run_` followed by 32 hex characters, as
`not_in_experiment` when the Experiment's table does not reference it, and as
`shared_with_other_experiment` when another registered Experiment's table
references it. An unknown Experiment SHALL be HTTP 404.

#### Scenario: Plan counts size

- **WHEN** a plan is requested for 47 runs of the Experiment
- **THEN** it reports 47 runs, their total file count and total bytes
- **AND** no run folder or table changed.

#### Scenario: Run of another Experiment

- **WHEN** the list contains a run that the Experiment's table does not reference
- **THEN** that run is skipped as `not_in_experiment` and is not counted.

#### Scenario: Shared run

- **WHEN** a requested run is also referenced by another registered Experiment
- **THEN** it is skipped as `shared_with_other_experiment`.

### Requirement: Delete requires the plan and the confirmed count

`POST /api/research/experiments/{experiment_id}/runs/delete` SHALL accept the same
list, the `plan_token` and a `confirm_run_count`. The service SHALL recompute the
plan; if its token differs from the supplied token, or the planned `run_count`
differs from `confirm_run_count`, it SHALL change nothing and answer HTTP 409
`plan_stale`. The token SHALL depend on the Experiment id, the deletable run ids
with their file counts and sizes, the skipped list and the content hash of the
result table, and SHALL NOT depend on server state.

#### Scenario: Table changed after the plan

- **WHEN** the result table changes between plan and delete
- **THEN** delete answers 409 `plan_stale` and deletes nothing.

#### Scenario: Wrong confirmed count

- **WHEN** `confirm_run_count` is not the planned run count
- **THEN** delete answers 409 `plan_stale` and deletes nothing.

### Requirement: Delete removes whole runs and clears run_id

Delete SHALL remove each planned run folder as a whole and SHALL empty the
`run_id` cell of every row that referenced a deleted run, including runs reported
as `already_absent`. It SHALL NOT modify any other cell, the manifest, the registry,
other Experiments, `batches/` or runs that were not selected. A deleted run SHALL
NOT remain partially present in `<artifacts_root>` at any time visible to the run
routes: folders are first moved atomically into a hidden folder under the artifacts
root and removed after the table is rewritten.

#### Scenario: Run list stays valid

- **WHEN** runs are deleted
- **THEN** `GET /api/research/runs` lists the remaining runs without error
- **AND** the deleted `run_id` is not listed.

#### Scenario: Other cells unchanged

- **WHEN** the table is rewritten
- **THEN** every cell except the cleared `run_id` cells is byte-identical to the
  table before.

#### Scenario: Open a deleted run

- **WHEN** the run routes are asked for a deleted `run_id`
- **THEN** they answer 404 `RunNotFound` as for any missing run.

### Requirement: Backup, atomic rewrite and journal

Before the table is rewritten the service SHALL keep a copy named
`runs.pre_delete_<UTC>.csv` (using the table's own file name stem) in the Experiment
folder, SHALL write the new table to a temporary file and rename it over the old one,
and SHALL append one line to `runs_deleted.jsonl` in the Experiment folder with the
UTC time, run ids, counts, bytes and backup name.

#### Scenario: Interrupted write

- **WHEN** the process stops while the new table is being written
- **THEN** the previous table is still intact.

### Requirement: Repeatable after interruption

Repeating a delete request after an interruption SHALL complete it: runs already
moved or removed are reported as `already_absent`, their `run_id` is cleared, and
leftovers in the hidden folder are removed.

#### Scenario: Crash after folders moved

- **WHEN** folders were moved to the hidden folder but the table was not yet rewritten
- **THEN** repeating the same request clears the `run_id` cells and removes the folders.

### Requirement: Read routes stay read-only

The three Experiment read routes and the run read routes SHALL keep their behavior.
The two routes of this capability SHALL be the only write path to an Experiment
folder and to run folders from Research Service, and SHALL NOT be reachable through
the read routes.

#### Scenario: Read routes unchanged

- **WHEN** the existing read-route test suite runs
- **THEN** it passes without modification.
