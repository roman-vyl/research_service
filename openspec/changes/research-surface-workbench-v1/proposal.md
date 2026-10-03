## Why

Research results live in analysis folders under the research data root
(`manifest.json`, `runs.csv`, `findings.jsonl`, README, standalone HTML) with the
Engine run bundles they were produced from stored elsewhere. The workbench can
show neither, and a result row cannot be opened as a run.

The domain model this change fixes:

- **Experiment** is the persisted research dataset: a frozen research setup plus
  its materialized result table. It is not an HTML file and not a UI view.
- **Run** is the detailed execution artifact of one materialized point of an
  Experiment, stored once at `research/runs/<run_id>/`.
- **Surface** is only the name of the workbench's interactive view over an
  Experiment (the user fixes some dimensions and sees a two-dimensional
  projection).
- **HTML** is a standalone presentation artifact generated from the same data;
  it is never parsed and never part of identity or resolution.

Facts established on the local research data (2026-10-03):

- Both existing EMA500 `runs.csv` files are already canonical result tables:
  ratio_4d has 12 672 rows, each with a unique `run_id`; trailing geometry has
  240 120 rows with no `run_id` column. Neither has duplicate dimension keys.
  The ratio_4d HTML data equals its `runs.csv` row for row.
- `research/runs` and `research/analysis` are on one volume; run ids
  (`run_` + uuid4 hex) have no conflicting copies; 4 060 identical copies exist.
- Research Service already reads a run at `<artifacts_root>/<run_id>/`; only the
  historical bundles that sit elsewhere are unreachable.
- `GET /api/research/runs` is called by the frontend only for the startup
  "newest run" selection and the run dropdown (and by Composer after a
  backtest to refresh that list); it reads and hashes every bundle in the root.
- ratio_4d is assembled from 7 batches with 7 different market windows and
  `market_data_hash` values (recorded per row); an Experiment can therefore
  hold several market snapshots.
- Of the 415 Engine runs known for the trailing experiment, 15 have no row in
  the table (lock-then-trail variants), 400 map to a row by dimensions, 5 rows
  are hit by two runs, and only 350 match their row's metrics exactly (the 360
  SL3 confirmation runs used a later market window, 38 differ in trade count).
  `run_id` linking therefore needs an explicit parity rule, not a name match.

## What Changes

- Extend the existing `manifest.json` of an Experiment with one machine-readable
  block `result_schema` (result table, run id column, provenance, row-level
  columns, dimensions with units and grids, arms, metrics with formats). No new
  `experiment.json`, no new cells table, no rename of `runs.csv`.
- Add an explicit registry `research/analysis/experiments.json` listing the
  available Experiments and their manifest paths.
- Add a minimal read-only **Experiment API**: list, definition (manifest),
  results (columnar, filterable by dimension equality), findings.
- Make `research/runs/<run_id>/` the only physical location of a run. Research
  Service needs no run index, resolver, second root or fallback.
- Add the **Surface tab** (`Chart | Surface | Reports | Strategy Composer`): a
  visualisation of an Experiment's ready-made result table, with views declared
  by the manifest `view` descriptor, filters and a details panel per point; all
  state is local to the tab. Its only link to the workbench is the existing
  `setSelectedRunId(run_id)`, triggered by an explicit "Open run" action on a
  point that has a `run_id`; points without one show their metrics only.
- Make the context-bar run dropdown legacy (hidden, code kept, read-only run id
  shown). Workbench starts with `selectedRunId = null` and an explicit idle
  state; an optional `?run=<run_id>` URL value sets the initial selection.
  `/api/research/runs` is no longer called at startup and is kept unchanged.
- Define a controlled, staged **migration** of existing artifacts (inventory,
  dry-run, validation, normalization of referenced runs into
  `research/runs/<run_id>`, trailing `run_id` column, manifest schema,
  registry, parity validation, separate cleanup phase). The change specifies the
  migration; it moves nothing itself.

## Capabilities

### New Capabilities

- `research-experiments-v1`: Experiment bundle contract (manifest
  `result_schema`, result table, provenance, canonical run location),
  Experiment registry, read-only Experiment API, controlled migration.
- `research-workbench-surface-view-v1`: Surface tab, point details with an explicit
  run action, legacy run dropdown, startup without a run.

### Modified Capabilities

- None.

## Non-Goals

- Moving, deleting or rewriting any existing file as part of this specification.
- Any run index, resolver, `run_store`, second run root, symlink handling,
  background or snapshot index, root ranking, manifest-hash qualifier, run
  ambiguity API.
- A backend entity or API named Surface; a geometry-aggregates endpoint; a
  parallel cells table; changing `/api/research/runs`; changing the chart
  runtime or report loading dependencies.
- Running Engine backtests for result rows that have no run.

## Impact

- Research Service: experiment registry/manifest/results reader, Experiment
  router, validation, settings `RESEARCH_ANALYSIS_ROOT` (read-only), migration
  tooling.
- Research data: additive manifest block, nullable `run_id` column in the
  trailing `runs.csv`, `analysis/experiments.json`, runs normalized to
  `research/runs/<run_id>` (all in the later migration phase).
- Research Frontend (`research_frontend`): Surface view and provider, API client,
  context-bar change, startup change, tests.
- No Strategy Engine change.
