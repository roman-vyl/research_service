## 1. Experiment Backend (research_service)

- [x] 1.1 Models for the manifest `result_schema` (dimensions with units or grids, arms, metrics with formats, `view`, provenance constant or column, `row_columns`, `run_id_column`); analysis root derived as `<artifacts_root>/../analysis` (no new setting).
- [x] 1.2 Reader for `analysis/experiments.json` (`experiment_id` is the only identity; `test_id` is legacy) and `GET /api/research/experiments` returning it as is.
- [x] 1.3 `GET /api/research/experiments/{experiment_id}` (manifest).
- [x] 1.4 `GET /api/research/experiments/{experiment_id}/results`: columnar `{columns, rows, data}`; semantic ids translated through `result_schema` (multi-grid columns, grid selector, arm, `run_id`, provenance); optional `columns`, equality filters, 400 on unknown ids, rounded floats, mtime-keyed cache.
- [x] 1.5 Tests on small fixture experiments (dual grid with arms and `view`, single grid with a per-row market hash, constant and column provenance): slicing by semantic ids, column selection, 404, malformed table affecting only its experiment, missing run bundle not affecting anything, no Surface/cells/aggregates/findings routes, `/api/research/runs*` unchanged.
- [x] 1.6 Measure and record response size and time for the trailing experiment unfiltered and per SL. Measured (240 120 rows, 53 MB CSV, full semantic id columns): cold unfiltered 1.5 s, 33 MB JSON, 7.3 MB gzip; cached unfiltered 0.9 s; `sl=5` 0.16 s, 6.6 MB / 1.5 MB gzip; `sl=5` and `grid=R` 0.10 s, 3.7 MB / 0.84 MB gzip; one geometry 0.02 s; peak RSS about 0.5 GB for the loaded table.

## 2. One-time Preparation of Historical Data (research_service, not runtime)

- [x] 2.1 Inventory and dry-run script: report of bundles and planned moves into `<artifacts_root>/<run_id>`; identical-copy collapse; STOP on conflicting copies or folder/`run_id` mismatch; same-volume check; rollback journal. Run it and attach the report to the PR; nothing is moved.
- [x] 2.2 Normalization step (`prepare.py normalize`, dry-run by default, `--apply` renames with a rollback journal and refuses on STOP/missing/other volume) (rename with journal) for the runs referenced by the two EMA500 tables; not executed in this change.
- [x] 2.3 Dataset preparation: manifest `result_schema` with `view` for both EMA500 experiments, `analysis/experiments.json`, nullable `run_id` column in the trailing table with a backup; trailing link algorithm (confirmed by recorded spec and metrics, row market hash only if present, one run per row, report of every other pair); not executed in this change.
- [x] 2.4 Verification: table metrics unchanged, equal to the existing ratio_4d HTML data, every non-null `run_id` has a canonical bundle.
- [ ] 2.5 Cleanup of identical duplicates and historical symlinks as a separate step after explicit approval.

## 3. Out of Scope (recorded)

Frontend implementation (separate `research_frontend` change).

Publisher, HTML generator (including restoring the ratio_4d HTML generator),
findings API, catalog validation, run materialization for replay-only rows.

## 4. Verification

- [ ] 4.1 After the approved one-time preparation: every non-null `run_id` of the two datasets reads through the existing run API.
- [x] 4.2 Confirm `/api/research/runs*` behaviour and tests are unchanged.
