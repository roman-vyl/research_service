## 1. Research Service

- [ ] 1.1 Manifest model for `materialize` (template, bindings, result bindings, research policy) with load-time checks: binding path exists in the template, binding and result-binding columns exist in the table, every metric column has a result binding.
- [ ] 1.2 Row addressing by `coords` over `result_schema` dimensions, grids and arms; `row_not_found` / `ambiguous_row`.
- [ ] 1.3 Materializer: deep copy, JSON Pointer set, typed parse, Engine `/strategies/{id}/validate` client, `config_hash`.
- [ ] 1.4 `POST .../runs/calculate-plan` and `POST .../runs/calculate` with skip reasons, 409/422 errors and the stateless plan token as in `design.md`.
- [ ] 1.5 Job runner: one job at a time, grouping by market data hash, Engine batch calls of at most 1 000 variants through `RunBatchExperiment`, cancel between calls; `GET .../calculations/{job_id}` and `POST .../calculations/{job_id}/cancel`.
- [ ] 1.6 Parity gate with the fixed tolerance from `design.md` D7.
- [ ] 1.7 Publisher: per-Experiment lock (also taken by run deletion), row-stale check, backup, atomic rewrite of only the allowed cells, `runs_calculated.jsonl`.
- [ ] 1.8 Tests on fixture Experiments with a fake Engine: materialize per binding type, invalid binding/path, unbound metric, constant replay provenance rejected, plan skip reasons, stale token, parity pass and fail (integer exact, relative and near-zero cases, one empty value), publish changes only allowed cells, row stale after deletion, cancel, journal lines, read routes and run deletion tests unchanged.

## 2. Existing Surfaces (research machine, only on explicit command)

- [ ] 2.1 Check script (not in the service): materialize every row with a live run and compare `config_hash` with the spec in its `request.json`; report mismatches.
- [ ] 2.2 Write and verify the `materialize` block for one Engine Surface (`btcusdt_p.ema500.ratio_4d`) with 2.1.
- [ ] 2.3 Smoke on that Surface: Calculate a few rows whose run was deleted; check parity pass, published cells, backup, journal, Workbench.
- [ ] 2.4 Smoke on one replay Surface with a few rows; report how many pass the gate.

## 3. Out of Scope (recorded)

Frontend Calculate button, selection and job progress (`research_frontend`
change); Strategy Engine changes; recalculating rows with a live run; cleaning
diagnostic runs; recording the Engine version per run.
