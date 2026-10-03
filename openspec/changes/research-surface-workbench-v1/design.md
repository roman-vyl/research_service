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

Only what the selector needs: `experiment_id` (unique key in the registry),
`title`, `ticker`, `anchor` (grouping), relative `manifest` path. The manifest
`test_id` stays an experiment identity inside its folder and is not the
registry key (it is not unique across anchors). The registry never copies
manifest content. An experiment absent from the registry is simply not served.

### D4. Canonical run location

`run_id → <artifacts_root>/<run_id>/` is the only physical resolution rule and
what Research Service already implements. No index, resolver, fallback root,
second root, recursive discovery, symlink handling, snapshot, refresh, root
ranking or hash qualifier. Publishing an Experiment never moves a run. Runs
referenced by no Experiment are an ordinary state of the same store.

### D5. Experiment API (read-only)

- `GET /api/research/experiments` → registry entries plus `row_count` and
  `valid` (with violation text when invalid).
- `GET /api/research/experiments/{experiment_id}` → the manifest.
- `GET /api/research/experiments/{experiment_id}/results` → columnar JSON
  `{ "columns": [...], "rows": N, "data": [[...per column...]] }`. Optional
  `columns=` limits the columns; any dimension column given as
  `<column>=<value>` (repeatable) filters by equality. Float columns are
  rounded for transport; the table on disk is authoritative.
- `GET /api/research/experiments/{experiment_id}/findings` → the findings lines.

No cells endpoint, no aggregates endpoint, no backend axis semantics beyond
equality filtering. Justification for a compact filterable results endpoint: the
trailing table is 53 MB as CSV and 34 MB / 6.4 MB gzip as columnar JSON for all
rows, 6.7 MB / 1.3 MB for one SL, so the frontend requests one SL (or one SL
and grid) at a time; slicing, filters and geometry aggregates then run in the
browser. The table is cached per file mtime and size.

Validation (lazily, cached by mtime): registry and manifest parse; `result_schema`
well formed; the table header contains every declared column; dimension keys are
unique per arm; every non-empty `run_id` exists as
`<artifacts_root>/<run_id>/manifest.json`. An invalid experiment stays listed
as invalid and its data routes return a stable error naming the violation.

### D6. Workbench state and startup

- `selectedRunId` (existing) remains the only selected-run identity.
- `selectedExperiment` and the Surface controls live in a provider above the
  tabs, not in `WorkbenchContext`, and survive tab switches.
- Row click with `run_id` → `setSelectedRunId(run_id)` and nothing else; clicking
  the already selected run changes nothing. A row is shown selected iff its
  `run_id === selectedRunId`; there is no selected-row state. A row without
  `run_id` never changes the selection and shows that no detailed Engine run is
  available.
- Legacy run dropdown: behind a flag, off in production, marked as legacy and a
  candidate for removal; the context bar shows the selected run id as text.
- Startup (E1): `selectedRunId = null` and an explicit idle report status;
  Chart and Reports show "Select a row in the Surface view". `/api/research/runs`
  is not called at startup; it stays in the backend and the client unchanged.
  An optional `?run=<run_id>` URL value is the initial `selectedRunId`; the URL
  is updated when the selection changes, so reload keeps the run and tests get a
  deterministic run without a "newest run" default. Composer selects the run
  returned by a backtest directly, without re-reading the run list.
- Run-specific transient state is already reset by the existing run-change path;
  the Surface view writes none of it and never carries bar or trade focus
  between runs.
- Mounting: the Surface pane sits outside `WorkbenchGate`; the Chart pane stays
  mounted (hidden) while the Surface view is shown. Surface code imports nothing
  from chart or chart-runtime modules and never enables chart heavy I/O;
  selecting a run before Chart was ever opened loads only the report requests.

### D7. Migration (specified here, executed later)

Phases, each stopping on failure and none destructive until the last:

1. **Inventory** of all bundles under the research data root: path, `run_id`,
   `manifest.run_id`, size, manifest hash, references from registered result
   tables.
2. **Dry-run plan** (report only): target `research/runs/<run_id>` per
   referenced run; identical copies collapse to one; copies with different
   manifests STOP; run id and folder name mismatch STOP.
3. **Validation** before any move: files and sizes per manifest, same volume,
   no target collision with a different manifest.
4. **Normalization**: `rename` into `research/runs/<run_id>` with a rollback
   journal; identical duplicates are left in place for phase 7.
5. **Data edits**: nullable `run_id` column added to the trailing `runs.csv`
   (backup kept); `result_schema` added to both manifests; `experiments.json`
   created.
6. **Parity validation**: every non-empty `run_id` resolves to
   `research/runs/<run_id>`; every linked run's metrics equal its row (net PnL
   or return, trade count, PF, drawdown, long/short) and its market hash
   matches the row's; table metrics equal the existing HTML data.
7. **Cleanup** (separate, last, only after phase 6 passes and after explicit
   approval): remove identical duplicate copies, historical symlinks, and
   emptied folders.

Trailing `run_id` linking rule (needed because the mapping is not name-unique):
a run is linked to a row only if it matches the row by all dimension values and
its recorded metrics equal the row's. If several runs satisfy this, prefer the
run whose market hash equals the table's market window, then the lowest
`run_id`; the choice is written to the migration report. Runs that match a row
by dimensions but not by metrics (for example a later market window) and runs
with no row (lock-then-trail variants) are not linked.

## Obsolete after this model (checked against dependencies)

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

- Startup without a run changes behaviour pinned by several frontend tests;
  they are updated deliberately (task group 5) rather than kept alive through a
  hidden default.
- Until the migration runs, historical runs are not at the canonical location;
  rows with such `run_id` fail validation and the experiment is reported
  invalid, which is intended.
- Only 350 of 415 known Engine runs of the trailing experiment match their row
  exactly; the rest stay unlinked, so drill-down covers few trailing rows until
  Engine runs are produced for more rows (later request).
- Whole-table results responses are large without a filter; the frontend
  always filters (at least by SL).
