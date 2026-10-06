## Why

A Surface point can be computed in two ways: by a replay or a script (cheap,
millions of points) or by a real Engine run. Today the only way to compute a point
with Engine is a script on the research machine that knows how to turn a row's
coordinates into a full strategy spec. That knowledge lives outside the
Experiment: `manifest.json` describes the axes, metrics and some `fixed_params`
for a human, but it does not say which strategy the Surface studies. Two Surfaces
can have the same `width` axis and use different setup components. So neither
the frontend nor Research Service can build an Engine spec for a row on its own.

This change makes the Experiment manifest the machine-readable definition of the
research and adds a **Calculate** operation: for selected rows Research builds the
spec from the manifest, runs Engine, compares the Engine result with the metrics
already stored in the row, and only if they agree publishes the Engine result to
the row.

## What Changes

- The manifest gets an optional `materialize` block: a full `strategy_template`
  (a complete deployable strategy instance, every component and every parameter,
  including everything that is never on the Surface), `bindings` (row column →
  JSON Pointer in the template), `result_bindings` (row metric column → field of
  the Research run summary) and the `research_policy` (window, execution,
  accounting, managed policy flag). Everything that is not a binding is frozen by
  the Experiment.
- Materialize is mechanical: deep copy of the template, each binding copies the
  row value to its path, Engine validates the spec. Research Service has no
  knowledge of components; the frontend sends only the Experiment and the rows.
- Calculate is a transaction per row: materialize → Engine run → metric parity gate
  against the row's stored metrics → atomic publish to the row (Engine metrics,
  `provenance=engine`, new `run_id`). If the gate fails the row is not changed and
  the outcome is `parity_failed` with the differing metrics; the new run is kept
  as a diagnostic artifact and is not linked to the row.
- Routes: calculate plan, calculate (starts a job), job status, job cancel.
- "Calculated" is not stored. It is derived from `provenance=engine` and a
  non-empty `run_id`.

## Capabilities

### New Capabilities

- `research-experiment-materialize-v1`: the `materialize` manifest block, row
  addressing by coordinates, materialize semantics and its validation.
- `research-run-calculation-v1`: Calculate plan/job routes, parity gate, publish
  to the result table, failure outcomes, journal.

### Modified Capabilities

- None archived. This change depends on `research-experiments-v1`
  (`research-surface-workbench-v1`) and `research-run-deletion-v1`. It adds a
  second write path to the Experiment result table next to run deletion.

## Non-Goals

- Recalculating a row that has a `run_id`. Only rows with an empty `run_id` are
  calculated; whether a run folder exists plays no role.
- Changing a row's coordinates, adding rows to a Surface, or creating a Surface.
- Formulas or unit conversions in bindings. A derived value (for example TP =
  SL × ratio) must be a column of the table.
- Checking that a replay method matches Engine. Preliminary replay ↔ Engine
  parity is the user's responsibility when the Experiment is prepared.
- Configurable parity tolerance. The tolerance is fixed by this contract.
- Persistent "Calculated" status, separate `replay_*`/`engine_*` metric columns.
- A durable job queue that survives a service restart; parallel jobs.
- Writing `materialize` blocks for existing Surfaces (data migration, done per
  Surface on the research machine, see tasks).
- Any change to Strategy Engine (`/strategies/{id}/validate` and
  `/strategy-evaluations/range-batch` are used as they are) or to the frontend
  (separate `research_frontend` change).

## Impact

- Research Service: manifest model for `materialize`, a materializer, a
  calculation job runner on top of the existing batch path
  (`RunBatchExperiment`), four routes under
  `/api/research/experiments/{experiment_id}/`, a table publisher that rewrites
  the result table atomically, tests on fixture Experiments.
- Research data: `runs.csv` rows change after a passed gate (metrics, provenance
  cell, `run_id`, market identity cells); a backup `runs.pre_calculate_<UTC>.csv`
  and `runs_calculated.jsonl` appear in the Experiment folder; new run folders and
  a batch folder per job appear in the artifacts root.
- Strategy Engine load: `/range-batch` calls of at most 1 000 variants, so at most two per request of 2 000 rows.
