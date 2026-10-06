## 1. Research Service

- [x] 1.1 Manifest model for `materialize` (template, bindings, result bindings, research policy) with load-time checks: binding path exists in the template, binding and result-binding columns exist in the table, every metric column has a result binding.
- [x] 1.2 Row addressing by `coords` over `result_schema` dimensions, grids and arms; `row_not_found` / `ambiguous_row`.
- [x] 1.3 Materializer: deep copy, JSON Pointer set, typed parse, Engine `/strategies/{id}/validate` client, `config_hash`.
- [x] 1.4 `POST .../runs/calculate-plan` and `POST .../runs/calculate` with skip reasons, 409/422 errors and the stateless plan token as in `design.md`.
- [x] 1.5 Job runner: one job at a time, grouping by market data hash, Engine batch calls of at most 1 000 variants through `RunBatchExperiment`, cancel between calls; `GET .../calculations/{job_id}` and `POST .../calculations/{job_id}/cancel`.
- [x] 1.6 Parity gate with the fixed tolerance from `design.md` D7.
- [x] 1.7 Publisher: per-Experiment lock (also taken by run deletion), row-stale check, backup, atomic rewrite of only the allowed cells, `runs_calculated.jsonl`.
- [x] 1.8 Tests on fixture Experiments with a fake Engine: materialize per binding type, invalid binding/path, unbound metric, constant replay provenance rejected, plan skip reasons, stale token, parity pass and fail (integer exact, relative and near-zero cases, one empty value), publish changes only allowed cells, row stale after deletion, cancel, journal lines, read routes and run deletion tests unchanged.

## 2. Existing Surfaces (research machine, only on explicit command)

- [x] 2.1 Check script (not in the service): materialize every row with a live run and compare `config_hash` with the spec in its `request.json`; report mismatches. `scripts/check_materialize.py` (`suggest` and `check`, standard library only, read-only); it also compares identity and `research_policy` with `request.json`.
- [x] 2.2 Write and verify the `materialize` block for one Engine Surface (`btcusdt_p.ema500.ratio_4d`) with 2.1. Done on the Mac: 12 528 rows, all with a live run; four bindings (`min_current_width_atr`, `untouched_lookback`, `sl_atr_multiplier`, `tp_atr_multiplier`), no formulas; materialized `config_hash` equals `request.json` on 12 528/12 528 rows. The runs used six data windows (same start, different `to_ms`); the owner chose the window of 9 724 runs (`to_ms` 1790543700000), so 2 804 rows of five extension batches differ only in `range.to_ms` (accepted exception; Calculate refuses them on the market data hash). Block written to the manifest (backup `manifest.pre_materialize_20261006T171846Z.json`), check from the manifest identical, `runs.csv` sha256 unchanged, Experiment route 200 with `materialize`. `max_drawdown_pct → max_drawdown` is matched by name only; the check does not compare metrics.
- [x] 2.3 Smoke on that Surface: Calculate a few rows whose run was deleted; check parity pass, published cells, backup, journal, Workbench. Done on the Mac 2026-10-06 with research-service image 4a85892: three majority-window rows (width 3, lookback 20, ratio 4.0; SL 4, 5, 7) had their runs deleted with the Delete route, then `calculate-plan` 3/3 calculable and `calculate` job completed with 3 published. All 8 metrics equal the stored values exactly (difference 0, including `max_drawdown_pct`), so the `max_drawdown` mapping holds; provenance `engine`, new run bundles exist, backup `runs.pre_calculate_20261006T174010Z.csv`, 3 journal lines, `runs.csv` still 12 528 rows with only `run_id` changed in exactly 3 rows. The Workbench page was not opened.
- [ ] 2.4 Smoke on one replay Surface with a few rows; report how many pass the gate.

## 3. Out of Scope (recorded)

Frontend Calculate button, selection and job progress (`research_frontend`
change); Strategy Engine changes; recalculating rows with a live run; cleaning
diagnostic runs; recording the Engine version per run.
