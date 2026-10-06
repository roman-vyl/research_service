## Context

- `FilesystemExperiments` reads the result table into `_Table` through a cache keyed by
  (path, mtime_ns, size); the `run_id_column` is one of its text columns.
- A run lives at `<artifacts_root>/<run_id>/`; run ids match `run_` + 32 hex characters
  (`research-run-deletion-v1`). Deletion and Engine fills rewrite the table, so they
  change the table key.
- The route is called by the picker for every card (`size=cached`) and once when an
  Experiment is opened (`size=compute`).

## Decisions

### D1. Response

```json
{
  "experiment_id": "example.surface",
  "rows": 3000,
  "engine_runs": 1200,
  "distinct_run_ids": 1200,
  "size": {
    "bytes": 50100000000,
    "run_bytes": 50000000000,
    "experiment_folder_bytes": 100000000,
    "missing_runs": 0,
    "computed_at": "2026-10-06T07:30:00Z"
  }
}
```

`rows` is the number of table rows, `engine_runs` the rows with a non-empty `run_id`,
`distinct_run_ids` the distinct non-empty `run_id`. `size` is `null` in `cached` mode
when not computed for the current table key.

### D2. Size

`run_bytes` sums `lstat` sizes of every file under `<artifacts_root>/<run_id>/` for each
distinct referenced run id. A run id that does not match the run id pattern, a path
that is a symbolic link, or a folder that does not exist counts in `missing_runs` and
adds nothing; symbolic links are never followed. `experiment_folder_bytes` sums the
files under the folder that holds the manifest (table, backups, journal, manifest).
`bytes` is their sum. Nothing lists `artifacts_root`, opens or hashes a run file, or
uses the code behind `GET /api/research/runs`.

### D3. Cache

In memory, keyed by the same (table path, mtime_ns, size) key as the results cache,
a few dozen entries, oldest dropped first. Nothing is written to disk. Computing is
serialized by a lock so that two simultaneous `compute` requests for the same table
walk it once.

### D4. Errors

Unknown Experiment: 404 `experiment_not_found`. Invalid `size` value: 422 (FastAPI query
validation). An invalid manifest or table: the existing `invalid_experiment` error.

## Risks / Trade-offs

- The first `compute` of a large Experiment stats every file of its runs; slow but
  bounded to that Experiment and triggered only by opening it.
- The cache is lost on restart; the picker shows "size not computed yet" until each
  Experiment is opened again. A persisted cache would make the route write.
