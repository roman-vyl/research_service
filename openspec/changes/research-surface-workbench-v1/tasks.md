## 1. Experiment Contract and Registry (Research Service)

- [ ] 1.1 Setting `RESEARCH_ANALYSIS_ROOT` (read-only, default `/data/analysis`).
- [ ] 1.2 Models and validation for the manifest `result_schema` (dimensions with units or grids, arms, metrics with formats, provenance constant or column, `row_columns`, `run_id_column`).
- [ ] 1.3 Registry reader for `analysis/experiments.json`: `experiment_id` is the only identity (also recorded in the manifest; `test_id` is legacy only), relative manifest path; unregistered folders are not served.
- [ ] 1.4 Validation cached by file mtime and size: header columns, dimension-key uniqueness per arm, every non-empty `run_id` has `<artifacts_root>/<run_id>/manifest.json`; invalid experiments stay listed as invalid.
- [ ] 1.5 Tests on small fixture experiments: dual grid with arms, single-grid with per-row market hash, constant and column provenance, missing unit, missing run bundle, duplicate keys.

## 2. Experiment API

- [ ] 2.1 `GET /api/research/experiments` (registry entries, `row_count`, validity).
- [ ] 2.2 `GET /api/research/experiments/{experiment_id}` (manifest).
- [ ] 2.3 `GET /api/research/experiments/{experiment_id}/results`: columnar `{columns, rows, data}`; semantic dimension/metric ids translated through `result_schema` (multi-grid columns, grid selector, arm, `run_id`, provenance); optional `columns`, equality filters, 400 on unknown ids, rounded floats, mtime-keyed cache.
- [ ] 2.4 `GET /api/research/experiments/{experiment_id}/findings`.
- [ ] 2.5 Tests: slice by SL, column selection, 404, invalid-experiment error; assert no Surface, cells or aggregates routes exist and `/api/research/runs*` is unchanged.
- [ ] 2.6 Measure and record response size and time for the trailing experiment unfiltered, per SL, and per SL without the ATR grid.

## 3. Migration Tooling (written and dry-run only until approved)

- [ ] 3.1 Inventory script: all bundles under the research data root with run id, folder name, `manifest.run_id`, size, manifest hash, references from registered result tables.
- [ ] 3.2 Dry-run planner and report: target `<artifacts_root>/<run_id>` per referenced run, identical-copy collapse, STOP on conflicting copies or folder/`run_id` mismatch, same-volume check, rollback journal format.
- [ ] 3.3 Trailing link planner: classify (run, row) pairs as CONFIRMED / POSSIBLE / NO LINK (spec-declared dimensions, metric equality, row market hash only if the row has one); write `run_id` only for exactly one CONFIRMED run per row; report all other pairs.
- [ ] 3.4 Data-edit step (manifest `result_schema` for both EMA500 experiments, nullable `run_id` column in the trailing table with backup, `experiments.json`), not executed in this change.
- [ ] 3.5 Parity validator: every non-empty `run_id` resolves, linked-run metrics equal rows, market hash matches, table equals existing HTML data.
- [ ] 3.6 Cleanup as a separate step requiring explicit approval after parity passes.
- [ ] 3.7 Run phases 1–2 as dry runs and attach the reports to the PR; no file is moved.

## 4. Future Generator / Publisher

- [ ] 4.1 Runs are created at `<artifacts_root>/<run_id>` and never moved by publication.
- [ ] 4.2 Publication writes the Experiment folder (manifest with `result_schema`, result table, findings, README, HTML), validates referenced runs exist, then adds the registry entry.
- [ ] 4.3 HTML is generated from the manifest and result table; restore the generator of the ratio_4d HTML (not present in any repository).

## 5. Surface View (research_frontend)

- [ ] 5.1 Types and API client for the Experiment list, manifest, results (filtered), findings.
- [ ] 5.2 `WorkbenchTab` `"surface"`; order `Chart | Surface | Reports | Strategy Composer`; Surface pane outside `WorkbenchGate`; gated Chart/Reports subtree kept mounted and hidden.
- [ ] 5.3 Provider above the tabs for `selectedExperiment` and controls; no selected-run or selected-row state.
- [ ] 5.4 Components driven by `result_schema`: Experiment selector, generic 2D projection over any two dimensions, metric selection, AND-filters with greyed rows; capability-gated parts: arm/baseline/difference only with `arms`, grid switch, filmstrip and geometry map (frontend aggregates) only with compatible multi-grid trigger/distance dimensions. Components use semantic ids only.
- [ ] 5.5 Row click: with `run_id` call `setSelectedRunId` (no-op if equal); without it show the note; highlight by `run_id === selectedRunId`; provenance label from the declared provenance.
- [ ] 5.6 Context bar: run `<select>` behind a legacy flag (off) with a deprecation comment; selected run id as read-only text.
- [ ] 5.7 Startup: initial `selectedRunId` null (or from `?run=`), idle report status and idle Chart/Reports states, URL kept in sync, no `/api/research/runs` call at startup; Composer selects the backtest run directly.
- [ ] 5.8 Update the tests that pin the old startup behaviour (`workbenchLoad`, `App`, `chartEventsDisplayLoad`, `chartEventsDistantTradeDisplay`, `ComposerPanel.runBacktest`) and the Playwright suites to select a run through `?run=`.
- [ ] 5.9 New tests:
  - static guard: `src/features/surface/**` imports nothing from `features/chart/**` or `features/workbenchChartRuntime/**`;
  - selection before Chart was opened makes only detail, trades, metrics and managed-policy-events requests;
  - selection through Surface and through the URL produce the same request sequence and the same trade/bar defaults;
  - Chart → Surface → Chart without a run change does not remount the Chart pane and makes no extra market requests;
  - Retry keeps the selected run; a row without `run_id` never calls `setSelectedRunId`; no `/runs` call at startup;
  - existing `workbenchChartRuntime` unit tests pass unchanged.

## 6. Verification

- [ ] 6.1 After approved migration: open a sample of ratio_4d rows end to end (row → Chart → Reports) and the linked trailing rows.
- [ ] 6.2 Confirm `/api/research/runs*` behaviour and tests are unchanged.
