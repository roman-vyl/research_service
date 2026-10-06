## 1. Research Service

- [x] 1.1 Candidate identity: required coordinate keys from `result_schema`, canonical values, `candidate_id`; 400 `invalid_coords`.
- [x] 1.2 Row resolution by coordinates through the results cache; 404 `row_not_found`, 409 `ambiguous_row`.
- [x] 1.3 Row fingerprint over the fixed field list (D4) and the snapshot (D5); strategy spec snapshot from the run's `request.json`, never failing the star.
- [x] 1.4 Shortlist store: `candidates.json` with lock, tmp + `os.replace`, journal line per change; missing file = empty; unreadable file = 500 `invalid_candidates_file`, not overwritten.
- [x] 1.5 Routes `GET`, `PUT`, `DELETE /api/research/candidates`; current state (D9) with the `(mtime_ns, size)` shortcut and `meaning` from the manifest. Measure a listing of 50 candidates over 3 changed tables. Measured on synthetic tables of 100 000 rows each (in the cloud container, not on real data): 50 stars 1.6 s; listing with unchanged tables 0.01 s; after all 3 tables changed 1.7 s with a cold cache (parse) and 0.7 s warm.
- [x] 1.6 Tests on fixture Experiments: idempotent star, same id for equal coordinates written differently (`6`, `6.0`), unstar and journal, run deleted → `same` with `run_id` null, provenance replay → engine with equal metrics → `same` with new provenance, metric changed → `changed`, auxiliary column or new manifest metric → `same`, row removed or Experiment unregistered → `missing`, duplicate coordinates → 409 on star and `ambiguous` on read, replay row (no run) → spec snapshot null, unreadable `request.json` → star succeeds, multi-grid and arm coordinates, no run folder listed and `GET /api/research/runs` not called.

## 2. Verification on real data (Mac, only on explicit command)

- [x] 2.1 Star one Engine point and one replay point on real Surfaces; list them; delete the Engine point's run with the delete route; listing shows `same` with no run. Confirmed by the owner on real data 2026-10-06 (research-service c155712): star, list, Chart and On Surface work; the run-deletion step was not performed on real data and is covered by the unit tests.

## 3. Out of Scope (recorded)

Frontend star and Candidates tab (`research_frontend` change), deployment or
runtime state, executable spec materialization.
