# Research Experiment Storage v1 Specification

## Purpose

Report, per Experiment, its strategy count, Engine run count and disk size through a
read-only route, without walking every run folder.

## Requirements
### Requirement: Storage route

`GET /api/research/experiments/{experiment_id}/storage` SHALL accept `size` with the
values `cached` (default) and `compute` and SHALL return `experiment_id`, `rows`,
`engine_runs`, `distinct_run_ids` and `size`. An unknown Experiment SHALL be HTTP 404;
any other `size` value SHALL be HTTP 422. The route SHALL NOT write any file.

#### Scenario: Counts from the table

- **WHEN** the table has 4 rows, 3 of them with a `run_id`, two of those equal
- **THEN** `rows` is 4, `engine_runs` is 3 and `distinct_run_ids` is 2.

#### Scenario: Invalid size value

- **WHEN** `size=all` is requested
- **THEN** the answer is HTTP 422.

### Requirement: Counts read no run folder

`rows`, `engine_runs` and `distinct_run_ids` SHALL be computed from the result table
only. With `size=cached` the route SHALL NOT read any run folder.

#### Scenario: Cached request before any compute

- **WHEN** `size=cached` is requested for an Experiment whose size was never computed
- **THEN** the counts are returned, `size` is `null` and no run folder is read.

### Requirement: Size of the Experiment

With `size=compute` the route SHALL return `size` with `bytes`, `run_bytes`,
`experiment_folder_bytes`, `missing_runs` and `computed_at`. `run_bytes` SHALL be the
sum of file sizes under each distinct referenced run folder; `experiment_folder_bytes`
the sum of file sizes under the Experiment folder; `bytes` their sum. A referenced run
whose id is invalid, whose path is a symbolic link or whose folder is missing SHALL be
counted in `missing_runs` and add no bytes. Symbolic links SHALL NOT be followed, the
artifacts root SHALL NOT be listed and run files SHALL NOT be opened.

#### Scenario: Missing run folder

- **WHEN** one referenced run folder does not exist
- **THEN** `missing_runs` is 1 and `run_bytes` is the size of the other run folders.

#### Scenario: Run used by another Experiment

- **WHEN** a run is referenced by two Experiments
- **THEN** its bytes count in the size of both.

### Requirement: Size cache

A computed size SHALL be kept in memory keyed by the result table path, modification
time and size, and SHALL be returned by later `cached` and `compute` requests while
that key holds. A changed table SHALL miss the cache. Nothing SHALL be persisted.

#### Scenario: Cached after compute

- **WHEN** `size=compute` was answered and then `size=cached` is requested
- **THEN** the same `size` is returned without reading run folders again.

#### Scenario: Table rewritten by a deletion

- **WHEN** runs are deleted after the size was computed
- **THEN** `size=cached` returns `size: null` and the new counts.

