# Research Run Deletion v1 Specification

## Purpose

Define deletion of whole Engine runs of an Experiment from Research Service while
the result rows (parameters, metrics, provenance) stay in the Experiment table.

## Requirements
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
`not_in_experiment` when the Experiment's table does not reference it, as
`shared_with_other_experiment` when another registered Experiment's table
references it, and as `not_a_directory` when the run path is a symbolic link. An unknown Experiment SHALL be HTTP 404.

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

### Requirement: Delete requires the plan token

`POST /api/research/experiments/{experiment_id}/runs/delete` SHALL accept the same
list and the `plan_token`. The service SHALL recompute the token; if it differs it
SHALL change nothing and answer HTTP 409 `plan_stale`. The token SHALL depend only
on the sorted deletable run ids and the content hash of the result table, and SHALL
NOT depend on server state.

#### Scenario: Table changed after the plan

- **WHEN** the result table changes between plan and delete
- **THEN** delete answers 409 `plan_stale` and deletes nothing.

#### Scenario: Selection changed after the plan

- **WHEN** the delete request lists different runs than the plan
- **THEN** delete answers 409 `plan_stale` and deletes nothing.

### Requirement: Delete removes whole runs and clears run_id

Delete SHALL remove each planned run folder as a whole and SHALL empty the
`run_id` cell of every row that referenced a deleted run, including runs reported
as `already_absent`. Deleting a run whose folder is already missing SHALL NOT be an
error. It SHALL NOT modify any other cell, the manifest, the registry, other
Experiments, `batches/` or runs that were not selected, and SHALL NOT delete files
inside a run folder separately from the folder.

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

#### Scenario: Already absent run

- **WHEN** a selected run's folder no longer exists
- **THEN** delete succeeds and its `run_id` cell is cleared.

### Requirement: Backup, atomic rewrite and journal

Before the table is rewritten the service SHALL keep a copy named
`runs.pre_delete_<UTC>.csv` (using the table's own file name stem) in the Experiment
folder, SHALL write the new table to a temporary file and rename it over the old one,
and SHALL append one line to `runs_deleted.jsonl` in the Experiment folder with the
UTC time, run ids, counts, bytes and backup name.

#### Scenario: Interrupted write

- **WHEN** the process stops while the new table is being written
- **THEN** the previous table is still intact.

### Requirement: Repeating a delete completes it

Repeating a delete after an interruption SHALL complete it: folders already removed
are treated as already deleted and the remaining `run_id` cells are cleared. The
service SHALL NOT require any recovery state for this.

#### Scenario: Stopped after some folders were removed

- **WHEN** some selected folders were removed but the table was not rewritten
- **THEN** repeating a plan and delete for the same runs clears every selected `run_id`.

### Requirement: Read routes stay read-only

The three Experiment read routes and the run read routes SHALL keep their behavior.
The two routes of this capability SHALL be the only write path to an Experiment
folder and to run folders from Research Service, and SHALL NOT be reachable through
the read routes.

#### Scenario: Read routes unchanged

- **WHEN** the existing read-route test suite runs
- **THEN** it passes without modification.
