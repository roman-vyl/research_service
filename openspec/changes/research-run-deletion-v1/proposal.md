## Why

Engine run bundles are the bulk of the research data (about 297 GB, most of it for
points that are junk). An Experiment's result table (`runs.csv`) already carries
every point's parameters and metrics, so Surface does not need the bundle to show a
point; only "Open run" does. Today the only way to free the space is to delete
folders by hand and leave `runs.csv` pointing at runs that no longer exist.

The model this change fixes is two-valued: a point either has a full run or it
does not. The row exists either way.

| Point | Metrics on Surface | `run_id` in the row | Open run |
| --- | --- | --- | --- |
| replay, no Engine run | replay | empty | no |
| Engine run stored | Engine | set | yes |
| Engine run deleted | Engine, unchanged | empty | no |

There is no "pruned" or "lightweight" run. A deleted run is a deleted run.

## What Changes

- Add a two-step, irreversible **delete runs** operation to Research Service for the
  runs of one Experiment: a dry-run plan (how many runs, files, bytes; what is
  skipped and why) and an apply step that needs the plan's token and the confirmed
  run count.
- Apply removes each selected run folder `<artifacts_root>/<run_id>/` whole and
  clears `run_id` in the Experiment's result table. No other cell of the table is
  touched; metrics and provenance stay exactly as they were.
- Before the table is rewritten, a backup `runs.pre_delete_<UTC>.csv` is kept next
  to it, the rewrite is atomic, and a line is appended to
  `runs_deleted.jsonl` in the Experiment folder.

## Capabilities

### New Capabilities

- `research-run-deletion-v1`: delete-plan and delete routes, the safety guards, the
  effect on the result table and on run resolution.

### Modified Capabilities

- None archived. This change depends on `research-experiments-v1`
  (`research-surface-workbench-v1`, merged in #18) and narrows exactly one of its
  statements: the Experiment routes stay read-only; the two routes added here are
  the only write path to an Experiment folder and to run folders.

## Non-Goals

- Calculating or restoring runs, a `materialize` manifest block, job queue,
  progress or cancel. That is a separate change after this one has been smoked on a
  real surface.
- A trash folder, undo, partial deletion of files inside a run, a "pruned" marker,
  a new HTTP status for deleted runs, changes to `GET /api/research/runs*` or to run
  reading.
- Deleting runs that no registered Experiment references, deleting batch folders,
  deleting an Experiment or its table rows.
- Any change to Strategy Engine or to the frontend (separate `research_frontend`
  change).

## Impact

- Research Service: one adapter that deletes, two routes under
  `/api/research/experiments/{experiment_id}/runs/`, tests on fixture data.
- Research data: `runs.csv` loses `run_id` values for deleted runs; a backup copy
  and `runs_deleted.jsonl` appear in the Experiment folder; run folders disappear.
- Deployment: the data root must be writable by Research Service (see design).
