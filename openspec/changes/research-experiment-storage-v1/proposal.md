## Why

The Workbench Surface picker needs, per Experiment, how many strategies it holds, how
many of them have an Engine run and how much disk it takes, so the owner can choose
what to clean up. No route reports this. `GET /api/research/runs` knows about runs
but reads and hashes every run folder (about 71 000) and must not be used for it.

The frontend side is `research_frontend` change `research-workbench-surface-storage-v1`,
whose design fixes the contract implemented here.

## What Changes

- Add `GET /api/research/experiments/{experiment_id}/storage?size=cached|compute`.
- Counts (`rows`, `engine_runs`, `distinct_run_ids`) come from the result table already
  held by the results cache; no run folder is read for them.
- `size` is the byte size of the distinct run folders the table references plus the
  Experiment folder, computed by stat-ing files only, cached in memory by the table key.
  `cached` never computes it (answers `null` on a miss); `compute` computes it on a miss.

## Capabilities

### New Capabilities

- `research-experiment-storage-v1`: the storage route, its counts, its size and cache.

### Modified Capabilities

- None. The route is read-only like the other Experiment read routes.

## Non-Goals

- Sizes per slice, cell or run; persisted caches; any write to the analysis folder.
- Any change to `GET /api/research/runs*`, run reading or run deletion.
- De-duplicating run folders shared between Experiments.

## Impact

Research Service: one adapter, one route, tests on fixture data. No setting, no
deployment change.
