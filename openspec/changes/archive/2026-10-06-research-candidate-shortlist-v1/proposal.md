## Why

The owner picks candidates for live trading by eye on the Surface. That choice is
stored nowhere. A Surface point has no own id, its `run_id` may be deleted
(`research-run-deletion-v1`) and its row index moves when slices are appended or
removed, so the choice cannot be stored in the result table or keyed by run.

This change adds a persistent shortlist: a Surface point (one strategy variant of
one Experiment) can be starred. A record exists = the point is picked; no record =
not picked. The record keeps a snapshot of what was picked, so the star survives
run deletion and table recalculation.

## What Changes

- A shortlist file `analysis/candidates.json` with atomic writes and a journal
  `analysis/candidates_journal.jsonl`.
- A candidate identity built by the backend from the Experiment manifest:
  `experiment_id` + canonical coordinates (every dimension, plus `grid` and `arm`
  when the schema has them). The client sends coordinates only; it never sends or
  computes `candidate_id`.
- At star time the record stores a snapshot of the row (all manifest metrics,
  provenance, `run_id`, row columns), a canonical fingerprint of the row content,
  the table key, and, when the row has a run, a copy of that run's strategy spec as
  a historical snapshot.
- Three routes: list, star, unstar. Listing reports per candidate whether the
  current row is still the picked one (`same`, `changed`, `missing`,
  `ambiguous`) and whether it currently has a run.

## Capabilities

### New Capabilities

- `research-candidate-shortlist-v1`: shortlist file, candidate identity, row
  fingerprint, snapshot, routes and the row state reported on read.

### Modified Capabilities

- None. Depends on `research-experiments-v1` (registry, manifest, result table)
  and is unaffected by `research-run-deletion-v1` except that a deleted run is
  reported as absent. The Experiment routes, the result table and run folders are
  never written by this change.

## Non-Goals

- Any deployment, runtime or trading state. The shortlist has no status or
  lifecycle field; whether a candidate is sent to Runtime or trades is a separate
  future entity, not a state of the star.
- Treating the stored strategy spec as a deployable specification. It is a
  historical snapshot of what was picked.
- Comments, bulk star, ranking, ordering by the user.
- Calculating runs or materializing a spec for replay rows.
- Changes to `/results`, `GET /api/research/runs*`, Strategy Engine or the
  frontend (separate `research_frontend` change).

## Impact

- Research Service: one adapter, three routes under `/api/research/candidates`,
  tests on fixture data.
- Research data: two new files in the analysis root. Experiment folders and run
  folders are not changed.
