## Context

See `proposal.md`. Facts the design relies on:

- Research Service reads a run via `FilesystemArtifactStore.read_run_file` at
  `<artifacts_root>/<run_id>/<file>`; `ReadResearchRuns.list_runs` reads and
  hashes every bundle in the root. In the compose stack the research data root is
  mounted at `/data` (`artifacts_root=/data/runs`, so `/data/analysis` is
  available).
- Frontend: one `selectedRunId` in `WorkbenchContext`; report loading depends on
  `selectedRunId` and `reloadToken` only; `reportLoadStatus` starts as
  `"loading"` and `WorkbenchGate` shows a loading view until a run loads;
  bootstrap fetches `/runs`, keeps the previous selection only if listed, else
  picks the first entry; the context bar renders a run `<select>` from `/runs`;
  Composer calls `refreshRunsAndSelectRun`. Tests that pin the startup behaviour:
  `workbenchLoad.test.tsx` ("selects the first entry from GET /runs"),
  `App.test.tsx`, `chartEventsDisplayLoad.test.tsx`,
  `chartEventsDistantTradeDisplay.test.tsx`, and the Playwright suites
  (`trade-focus*`, `diagnostics-acceptance`).
- Run-change lifecycle already resets the previous run's state: market owner,
  trace generation, run-keyed trace display cache, context overlay default, and
  trade/bar focus re-seeded to the new run's last closed trade.
- Existing result tables: ratio_4d `runs.csv` (26 columns, 12 672 rows,
  `run_id` and `instance_id` per row, per-row `market_data_hash`, `return_pct`
  and `max_drawdown_pct` as fractions, no `net_pnl`); trailing geometry
  `runs.csv` (34 columns, 240 120 rows, `arm`, `geometry_grid_unit`, trigger and
  distance in both ATR and R, `net_pnl`, fractions for return and drawdown, no
  `run_id`). `test_id` is not globally unique (ema500 and ema1000 both carry
  `width_x_untouched_x_stop_x_ratio_4d`).
- Size of the trailing results: CSV 53 MB. A columnar JSON with 10 dimension
  and 13 metric columns is 34 MB raw / 6.4 MB gzip for all 240 120 rows (parsed
  in about 70 ms in Node), 6.7 MB / 1.3 MB for one SL (48 024 rows), 4.1 MB /
  0.8 MB for one SL without the ATR grid. The existing standalone HTML embeds
  14.5 MB.

## Goals / Non-Goals

**Goals:** one persisted Experiment model; one physical run location; no run
resolution machinery; frontend renders a generic Experiment from manifest plus
result table; `selectedRunId` stays the only selected-run identity; chart runtime
untouched.

**Non-Goals:** see proposal.

## Decisions

### D1. Experiment bundle

```
research/analysis/<ticker>/<anchor>/<experiment>/
  manifest.json      authoritative machine-readable description (extended)
  runs.csv           authoritative materialized result table (name kept)
  findings.jsonl     interpretation, not data
  README.md          human notes, never needed by a program
  report.html        standalone presentation, never parsed
```

Names of folders and of the HTML are organisation only. Everything a program
needs is in `manifest.json` and the result table. `runs.csv` is not renamed:
the manifest names it (`result_schema.table`).

### D2. Manifest extension `result_schema`

One additive block in the existing manifest; existing keys (`test_id`,
`varied_params`, `search_space`, `fixed_params`, `metric_columns`, history, …)
stay as they are and are not interpreted by the frontend.

```json
"experiment_id": "btcusdt_p.ema500.ratio_4d",
"result_schema": {
  "contract_version": "research_experiment_result_schema.v1",
  "table": "runs.csv",
  "run_id_column": "run_id",
  "provenance": { "value": "engine" },
  "row_columns": { "market_data_hash": "market_data_hash" },
  "dimensions": [
    { "id": "width",    "label": "Stack width",        "column": "min_current_width_atr", "unit": "ATR" },
    { "id": "lookback", "label": "Untouched lookback", "column": "untouched_lookback",    "unit": "bars" },
    { "id": "sl",       "label": "Initial SL",         "column": "sl_atr_multiplier",     "unit": "ATR" },
    { "id": "tp_ratio", "label": "TP / SL",            "column": "tp_sl_ratio",           "unit": "R" }
  ],
  "view": [
    { "id": "main", "x": "lookback", "y": "width", "controls": ["sl", "tp_ratio"], "default_metric": "return_pct" }
  ],
  "metrics": [
    { "column": "return_pct",       "label": "Return",  "format": "fraction" },
    { "column": "profit_factor",    "label": "PF",      "format": "number" },
    { "column": "max_drawdown_pct", "label": "Max DD",  "format": "fraction" },
    { "column": "cumulative_net_r", "label": "Cum. R",  "format": "number", "unit": "R" }
  ]
}
```

Trailing geometry (dual grid, arms, row-level provenance column absent, a
constant provenance):

```json
"result_schema": {
  "contract_version": "research_experiment_result_schema.v1",
  "table": "runs.csv",
  "run_id_column": "run_id",
  "provenance": { "value": "replay" },
  "dimensions": [
    { "id": "width",    "column": "min_current_width_atr", "unit": "ATR" },
    { "id": "lookback", "column": "untouched_lookback",    "unit": "bars" },
    { "id": "sl",       "column": "sl_atr_multiplier",     "unit": "ATR" },
    { "id": "trigger",  "label": "Trigger T", "grid_column": "geometry_grid_unit",
      "grids": { "ATR": { "column": "trail_trigger_atr",  "unit": "ATR" },
                 "R":   { "column": "trigger_r",          "unit": "R" } } },
    { "id": "distance", "label": "Trail D",   "grid_column": "geometry_grid_unit",
      "grids": { "ATR": { "column": "trail_distance_atr", "unit": "ATR" },
                 "R":   { "column": "trail_distance_r",   "unit": "R" } } }
  ],
  "arms": {
    "column": "arm",
    "roles": { "trailing_no_tp": "treatment", "control_tp5r": "comparison",
               "fixed_tp_6r": "comparison", "fixed_tp_7r": "comparison",
               "fixed_tp_8r": "comparison", "fixed_tp_10r": "comparison" },
    "baseline": "control_tp5r",
    "match_on": ["width", "lookback", "sl"]
  },
  "view": [
    { "id": "cells", "x": "lookback", "y": "width", "controls": ["sl", "grid", "trigger", "distance"], "default_metric": "net_pnl", "filmstrip": "trigger" },
    { "id": "geometry", "x": "distance", "y": "trigger", "controls": ["sl", "grid"], "aggregate_over": ["width", "lookback"], "default_metric": "net_pnl" }
  ],
  "metrics": [ { "column": "net_pnl", "label": "Net PnL", "format": "number", "unit": "USDT" },
               { "column": "return_pct", "label": "Return", "format": "fraction" } ]
}
```

Rules: dimensions that exist in several units declare each grid and its
columns, and the frontend never infers a relation from column names; the
`geometry_grid_unit` column states which grid defined the row (both unit
columns are filled for every treatment row); `format: "fraction"` means the
stored value is a fraction (0.25 = 25 %), never inferred from a `_pct` suffix;
comparison rows are matched to treatment rows on `match_on`.

`provenance` is `{ "value": <origin> }` for a constant origin or
`{ "column": <name> }` for a per-row origin. Allowed origins: `engine`,
`replay`, extendable by later changes. Provenance is stored data; it is
**never** derived from whether `run_id` is present. `run_id` only says whether a
materialized Engine run exists for drill-down, which is orthogonal to how the
row's metrics were produced.

Row-level market provenance: a table may carry its own market columns
(`row_columns`), declared by the manifest and treated as authoritative;
ratio_4d keeps its per-row `market_data_hash` (7 values). The manifest does not
claim one experiment-wide hash or window. An optional informational `market`
object may list the snapshots.

### D3. Experiment registry

`research/analysis/experiments.json`:

```json
{ "registry_version": 1,
  "experiments": [
    { "experiment_id": "btcusdt_p.ema500.ratio_4d", "title": "Fixed SL × TP ratio",
      "ticker": "BTCUSDT.P", "anchor": "EMA500",
      "manifest": "BTCUSDT.P/ema500/width_x_untouched_x_stop_x_ratio_4d/manifest.json" } ] }
```

Only what the selector needs: `experiment_id`, `title`, `ticker`, `anchor`
(grouping), relative `manifest` path. `experiment_id` is the one identity of an
Experiment in the new system (for example `btcusdt_p.ema500.trailing_geometry_4d`)
and is also recorded in the manifest. `test_id` in the existing manifest is only
the legacy domain test name (for example
`width_x_untouched_x_stop_x_trailing_geometry_4d`); it is not unique across
anchors, is not an identity, and no route or registry key uses it. The registry
never copies manifest content. An experiment absent from the registry is not
served.

### D4. Canonical run location

`run_id → <artifacts_root>/<run_id>/` is the only physical resolution rule and
what Research Service already implements. No index, resolver, fallback root,
second root, recursive discovery, symlink handling, snapshot, refresh, root
ranking or hash qualifier. Publishing an Experiment never moves a run. Runs
referenced by no Experiment are an ordinary state of the same store.

### D5. Experiment API (read-only, three routes)

- `GET /api/research/experiments` → the contents of `experiments.json`, nothing
  else (no table reads, no validation, no row counts).
- `GET /api/research/experiments/{experiment_id}` → the manifest.
- `GET /api/research/experiments/{experiment_id}/results` → columnar JSON
  `{ "columns": [...], "rows": N, "data": [[...per column...]] }`. The API speaks
  the manifest's semantic ids: filters are `<dimension id>=<value>` (repeatable,
  equality, for example `sl=5`, `grid=R`, `trigger=7`) and `columns=` selects ids;
  the backend translates ids to physical CSV columns through `result_schema`
  (every unit column of a multi-grid dimension, the grid selector, the arm,
  `run_id`, provenance). Response columns are semantic ids, so the frontend never
  uses physical column names. An unknown id is HTTP 400. Floats are rounded for
  transport; the table on disk is authoritative.

That is the whole new backend: read `experiments.json`, read `manifest.json`,
read `runs.csv` through a small filter/project adapter (cached by file mtime and
size). Justification for a filterable columnar results route: the trailing table
is 53 MB as CSV and 34 MB / 6.4 MB gzip as columnar JSON for all rows, 6.7 MB /
1.3 MB for one SL, so the frontend requests one SL at a time and does slicing,
filters and aggregates in the browser.

Errors are reported where they occur: a malformed manifest or table returns a
stable error naming the problem when that experiment is opened; there is no
validation cascade, no catalog `valid` flag, and a `run_id` whose bundle is
missing does not invalidate anything. `run_id` is optional drill-down: "Open run"
calls the existing run API, which returns 404 for a missing bundle.

Findings stay as `findings.jsonl` next to the manifest and are not served by
this change. No Surface, cells, aggregates or findings route exists.

**Root setting.** No new setting. The data root already holds
`runs/` (`artifacts_root`) and `configs/` (`configs_root`) under one mount
(`/data` in the compose stack); the analysis root is `artifacts_root.parent /
"analysis"`, so `runs/` and `analysis/` come from one configured root and cannot
drift apart. Checked in `runtime/settings.py` and `bbb_stack/docker-compose.yml`:
the whole research data directory is mounted at `/data`, so `/data/analysis` is
available without a deployment change.

### D6. Workbench frontend (kept deliberately small)

Boundary: the Surface tab visualises ready-made metrics; its only link to the
workbench is the existing `setSelectedRunId(run_id)`.

```
App
├── Chart                existing
├── Surface              new: ExperimentSelector, SurfaceControls, SurfacePlot, CellDetails
├── Reports              existing
└── Strategy Composer    existing
```

- **State.** All Surface state (experiment, metric, view, controls, filters,
  selected point) is local to `SurfaceView`. No provider and no global state: the
  Surface pane is mounted-and-hidden like the Chart pane, so its state survives
  Chart/Surface/Reports switches. As with Chart today, visiting the Composer
  (which `App` renders instead of the tab panes) discards it.
- **Placement.** The Surface pane renders outside `WorkbenchGate`, because the
  gate shows loading/error while no run is selected and Surface must work then.
- **Point model.** One model for the frontend: coordinates, metrics, optional
  `run_id`; no separate kinds for replay or Engine points. Provenance is a label
  taken from the declared provenance.
- **Click.** A point click only opens local CellDetails. With a `run_id` the
  details offer "Open run", which calls `setSelectedRunId(run_id)` and
  `setActiveTab("chart")`; without one it says no detailed Engine run is
  available. `selectedRunId` is never used as the identity of a point and no
  highlight is derived from it.
- **Views.** The manifest `view` descriptor declares each view (x, y, control
  dimensions, default metric, optional aggregation dimensions); the frontend does
  not offer arbitrary axes. Trailing: a width × lookback view (controls SL,
  trigger, distance, grid) and an aggregated trigger × distance map (aggregates
  over width and lookback); ratio: one width × lookback view (controls SL and
  TP ratio). Aggregates (median, counts, share passing, difference to the
  baseline arm) are plain operations over table columns. The trailing
  width × lookback view declares `"filmstrip": "trigger"`: a row of small
  copies of the heatmap, one per trigger value at the selected distance, which
  helps read the geometry; it is declared per view, not derived, and no other
  presentation is added to the descriptor (no layouts, widgets, formulas or
  expressions).
- **Legacy dropdown.** The run `<select>` moves behind a flag (off), marked
  legacy; the context bar shows the selected run id as text.
- **Startup.** `selectedRunId = null` with an explicit idle report status;
  Chart and Reports show an idle message. `/api/research/runs` is not called at
  startup (route and client function unchanged). A `?run=<run_id>` URL value is
  the initial `selectedRunId` and the URL follows later selections, so reload
  keeps the run and tests get a deterministic run. Composer selects the
  backtest's run directly.
- **Existing behaviour relied on, no new code.** On a run change the existing
  path already drops the previous run's market owner, trace generation, trace
  cache, overlay default and re-seeds trade/bar focus; the Surface tab neither
  adds nor writes any of it.

### D7. One-time preparation of historical data (not runtime)

This is a controlled, one-time preparation of existing artifacts, not a Research
Service capability. After it, runtime code knows only: registry, manifest,
result table with optional `run_id`. Steps, each stopping on failure, nothing
destructive until the last:

1. **Inventory and dry-run.** Report of all bundles (path, `run_id`, folder name
   vs `manifest.run_id`, size, manifest hash, references from the two result
   tables) and the planned moves into `<artifacts_root>/<run_id>`; identical
   copies collapse; conflicting copies, or a folder name different from
   `manifest.run_id`, STOP. Nothing is moved.
2. **Normalize** the referenced historical bundles into
   `<artifacts_root>/<run_id>` by rename with a rollback journal. Run ids do not
   change.
3. **Prepare the two EMA500 datasets.** Add `result_schema` (with `view`) to both
   manifests; create `analysis/experiments.json`; add the nullable `run_id`
   column to the trailing table with the confirmed links (below).
4. **Verify.** Table metrics unchanged; table equals the existing HTML data
   where it exists (ratio_4d); every non-null `run_id` has a bundle at the
   canonical location.
5. **Cleanup** of identical duplicates and historical symlinks, separately and
   only after explicit approval.

Link algorithm for the trailing table (migration-only vocabulary, absent from
the runtime model and from the manifest). A false link is worse than a missing
one, so each candidate (run, row) pair is classified:

- CONFIRMED: the run's own `request.json` declares the row's dimension values
  (width, lookback, SL, trigger, distance, grid), the run's recorded metrics equal
  the row's, and, only if the row has an authoritative `market_data_hash`, the
  run's market hash equals it;
- POSSIBLE: matches only by dimensions and numbers, or several runs are CONFIRMED
  for one row;
- NO LINK: no row, or the numbers differ (later market window, lock-then-trail
  variants).

`run_id` is written only for CONFIRMED pairs with exactly one run per row; there
is no market-hash tie-break and no table-wide market window is assumed; all
other pairs are listed in the report. Losing a drill-down is acceptable.

## Obsolete after this model (checked against dependencies)

Also removed in the reduction pass: eager run validation, catalog `valid` and
violation text, `row_count`, the findings route, the `RESEARCH_ANALYSIS_ROOT`
setting, the publisher and HTML-generator tasks, and CONFIRMED/POSSIBLE/NO LINK
as part of any contract.


Multi-root run index, recursive discovery, symlink and `realpath` handling,
background build, snapshot, directory-mtime refresh, root ranking,
`manifest_sha256` qualifier, `run_ambiguous` and `run_index_building` errors,
modified `research-results-bff-v1` run-route requirements, Surface as a backend
entity and `/surfaces` naming, the geometry-aggregates endpoint, `run_links.csv`
and any parallel cells table, mandatory `cell_id`, `run_store` or any
movement of runs between roots, `empty run_id = replay`. Checked: nothing else
in this change depends on them; the run-read routes already satisfy the
canonical-location rule.

## Risks / Trade-offs

- Startup without a run changes behaviour pinned by several frontend tests; they
  are updated deliberately (task group 4) rather than kept alive through a hidden
  default.
- Until the one-time preparation runs, historical runs are not at the canonical
  location; "Open run" for them returns 404 (nothing else breaks).
- Only 350 of 415 known Engine runs of the trailing experiment match their row
  exactly and not every one may be confirmed; drill-down covers few trailing rows
  until Engine runs are produced for more rows (later request).
- Whole-table results responses are large without a filter; the frontend always
  filters (at least by SL).
