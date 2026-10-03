## 1. Experiment Backend (Research Service)

- [ ] 1.1 Models for the manifest `result_schema` (dimensions with units or grids, arms, metrics with formats, `view`, provenance constant or column, `row_columns`, `run_id_column`); analysis root derived as `<artifacts_root>/../analysis` (no new setting).
- [ ] 1.2 Reader for `analysis/experiments.json` (`experiment_id` is the only identity; `test_id` is legacy) and `GET /api/research/experiments` returning it as is.
- [ ] 1.3 `GET /api/research/experiments/{experiment_id}` (manifest).
- [ ] 1.4 `GET /api/research/experiments/{experiment_id}/results`: columnar `{columns, rows, data}`; semantic ids translated through `result_schema` (multi-grid columns, grid selector, arm, `run_id`, provenance); optional `columns`, equality filters, 400 on unknown ids, rounded floats, mtime-keyed cache.
- [ ] 1.5 Tests on small fixture experiments (dual grid with arms and `view`, single grid with a per-row market hash, constant and column provenance): slicing by semantic ids, column selection, 404, malformed table affecting only its experiment, missing run bundle not affecting anything, no Surface/cells/aggregates/findings routes, `/api/research/runs*` unchanged.
- [ ] 1.6 Measure and record response size and time for the trailing experiment unfiltered and per SL.

## 2. One-time Preparation of Historical Data (not runtime)

- [ ] 2.1 Inventory and dry-run script: report of bundles and planned moves into `<artifacts_root>/<run_id>`; identical-copy collapse; STOP on conflicting copies or folder/`run_id` mismatch; same-volume check; rollback journal. Run it and attach the report to the PR; nothing is moved.
- [ ] 2.2 Normalization step (rename with journal) for the runs referenced by the two EMA500 tables; not executed in this change.
- [ ] 2.3 Dataset preparation: manifest `result_schema` with `view` for both EMA500 experiments, `analysis/experiments.json`, nullable `run_id` column in the trailing table with a backup; trailing link algorithm (confirmed by recorded spec and metrics, row market hash only if present, one run per row, report of every other pair); not executed in this change.
- [ ] 2.4 Verification: table metrics unchanged, equal to the existing ratio_4d HTML data, every non-null `run_id` has a canonical bundle.
- [ ] 2.5 Cleanup of identical duplicates and historical symlinks as a separate step after explicit approval.

## 3. Out of Scope (recorded)

Publisher, HTML generator (including restoring the ratio_4d HTML generator),
findings API, catalog validation, run materialization for replay-only rows.

## 4. Surface Tab (research_frontend)

- [ ] 4.1 Types and API client for the Experiment list, manifest, results (filtered by semantic ids), findings.
- [ ] 4.2 `WorkbenchTab` `"surface"`; order `Chart | Surface | Reports | Strategy Composer`; Surface pane mounted-and-hidden like Chart, rendered outside `WorkbenchGate`.
- [ ] 4.3 `SurfaceView` with local state only (experiment, metric, view, controls, filters, selected point); no provider, no global state.
- [ ] 4.4 Components: ExperimentSelector, SurfaceControls (units and ATR↔R conversion), SurfacePlot (heatmap, aggregated map and the declared trigger filmstrip from the manifest `view`), AND-filters with greyed points, CellDetails; baseline/difference only with `arms`.
- [ ] 4.5 CellDetails: with `run_id` an "Open run" action calling `setSelectedRunId(run_id)` and `setActiveTab("chart")`; without it the metrics and an "Engine run not available" note; provenance from the declared provenance; no use of `selectedRunId` as point identity.
- [ ] 4.6 Context bar: run `<select>` behind a legacy flag (off) with a deprecation comment; selected run id as read-only text.
- [ ] 4.7 Startup: initial `selectedRunId` null (or from `?run=`), idle report status and idle Chart/Reports messages, URL kept in sync, no `/api/research/runs` call at startup; Composer selects the backtest run directly.
- [ ] 4.8 Update the tests that pin the old startup behaviour (`workbenchLoad`, `App`, `chartEventsDisplayLoad`, `chartEventsDistantTradeDisplay`, `ComposerPanel.runBacktest`) and the Playwright suites to select a run through `?run=`.
- [ ] 4.9 New tests: static guard that `src/features/surface/**` imports nothing from `features/chart/**` or `features/workbenchChartRuntime/**`; no `/api/research/runs` call at startup; a point without `run_id` never calls `setSelectedRunId`; "Open run" calls it once with the `run_id`; Retry keeps the selected run; Surface state survives Chart ↔ Surface ↔ Reports; existing `workbenchChartRuntime` unit tests pass unchanged.

## 5. Verification

- [ ] 5.1 After approved migration: open a sample of ratio_4d rows end to end (row → Chart → Reports) and the linked trailing rows.
- [ ] 5.2 Confirm `/api/research/runs*` behaviour and tests are unchanged.
