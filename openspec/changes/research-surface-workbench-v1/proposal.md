## Why

Research results for parameter surfaces (for example BTCUSDT.P / EMA500
`width_x_untouched_x_stop_x_ratio_4d` and `width_x_untouched_x_stop_x_trailing_geometry_4d`)
exist only as canonical folders under the research data root (`manifest.json`,
`runs.csv`, `findings.jsonl`, copied run bundles) plus static local HTML
visualisations. The workbench cannot show them, and a surface cell cannot be
opened as a run:

- The HTML cells carry no run identity at all.
- Research Service reads run bundles only from the flat `<artifacts_root>/<run_id>/`
  layout. 12 672 historical runs referenced by `width_x_untouched_x_stop_x_ratio_4d/runs.csv`
  live only inside the canonical folder (`runs/<batch>/candidates/<run_id>/`)
  and are unreachable through `/api/research/runs/{run_id}`.
- Copies of the same run exist in several places. A scan on 2026-10-03 found
  78 842 run bundle directories for 68 485 distinct `run_id`s: 4 060 run ids
  have a byte-identical copy in both `<artifacts_root>` and a canonical folder,
  and 6 297 more resolve to one directory through symlinks. No run id currently
  has two different manifests, but nothing prevents it.
- Most rows of the trailing-geometry surface are Engine-exact replay results
  without any Engine run bundle (only 415 Engine runs exist for that
  surface, against 240 120 rows), so they must be shown
  honestly as replay rows, not as runs.

The goal is a workbench tab where one surface cell maps to exactly one run
when a run exists, without copying the existing data.

## What Changes

- Add a read-only **run index** over the primary artifacts root and configured
  additional roots (canonical research folders). It discovers run bundles in
  place without copying, deduplicates symlinked and byte-identical copies,
  identifies a run by `run_id` plus manifest SHA-256, and reports conflicts
  instead of guessing.
- Resolve every `/api/research/runs/{run_id}*` read route through the index, so
  historical batch and canonical runs open like any published run. The `/runs`
  list keeps its current scope (primary root only).
- Define a **research surface contract** (`research_surface.v1`): a
  `surface.json` beside an existing canonical test folder declaring market,
  axes and units, arms, and the cells table. Each cell row carries a
  deterministic `cell_id`, an optional `run_id` with `run_manifest_sha256`, and
  a `provenance` (`engine`, `replay`, `engine_confirmed_replay`).
- Add a read-only **surfaces API**: list surfaces, surface definition, cell
  slices, geometry aggregates, findings.
- Add a **Surface tab** to the Research Workbench frontend: width × lookback
  heatmap, axis sliders with explicit units, arm and comparison selection,
  AND-filters, geometry map, and click-through from a cell to its run in the
  Chart and Reports tabs.
- Provide a one-time migration script that adds `cell_id`, `run_id`,
  `run_manifest_sha256` and `provenance` to the two existing BTCUSDT.P / EMA500
  surfaces and writes their `surface.json`.

## Capabilities

### New Capabilities

- `research-run-index-v1`: read-only, multi-root, copy-free run bundle index
  with exact identity and conflict reporting.
- `research-surfaces-v1`: research surface contract and read-only surfaces API.
- `research-workbench-surface-tab-v1`: frontend Surface tab and cell-to-run
  navigation.

### Modified Capabilities

- `research-results-bff-v1`: run read routes resolve run bundles through the
  run index.

## Non-Goals

- Running Engine backtests for replay-only cells (materialization). Replay
  cells are shown as replay without drill-down; producing real runs for them is
  a later, explicit request and a separate change.
- Deleting, moving or rewriting existing run bundles or canonical folders.
  Cleanup of unreferenced copies is left to a later decision informed by the
  index report.
- Changing run bundle contents, batch execution, or the `/runs` list scope.

## Impact

- Research Service: new run index adapter and settings, index-backed run
  reads, new surfaces router and application service, readiness/diagnostics
  reporting of index state.
- Research data: additive `surface.json` and four additive columns in the
  existing `runs.csv` of the two EMA500 surfaces (written by the migration
  script; previous files kept as backups).
- Research Frontend (separate repository `research_frontend`): new tab,
  API client functions and types, components, tests.
- No Strategy Engine change.
