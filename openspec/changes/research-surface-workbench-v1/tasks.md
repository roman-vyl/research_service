## 1. Run Index (Research Service)

- [ ] 1.1 Add settings `RESEARCH_RUN_INDEX_EXTRA_ROOTS` (ordered, read-only) and document them; default empty.
- [ ] 1.2 Implement discovery of `run_<32 hex>/manifest.json` at any depth with symlink following, `realpath` de-duplication and `manifest_sha256` hashing.
- [ ] 1.3 Implement resolution (single manifest hash → lowest root rank, then smallest real path; several hashes → ambiguous) and qualified lookup by `manifest_sha256`.
- [ ] 1.4 Persist and reload the snapshot under `<artifacts_root>/.run_index/`; rescan roots whose directory mtimes changed; add bundles at publish time.
- [ ] 1.5 Background build at start; readiness states; `GET /api/research/run-index` report; `POST /api/research/run-index/refresh`.
- [ ] 1.6 Tests: symlinked copy, identical copies across roots, conflicting copies, qualifier mismatch, build-in-progress error, publish-time insertion, extra roots never written.

## 2. Index-backed Run Reads

- [ ] 2.1 Route `RunArtifactReader.read_run_file` and every `/api/research/runs/{run_id}*` route through the index, with optional `manifest_sha256`.
- [ ] 2.2 HTTP 409 `run_ambiguous` and 503 `run_index_building` error contracts.
- [ ] 2.3 Keep `/runs` and `/runs/latest` limited to the primary root.
- [ ] 2.4 Tests: canonical-folder run detail, trades, metrics, chart events and managed-policy events identical to the same bundle placed in the primary root.

## 3. Surface Contract and API

- [ ] 3.1 Pydantic models for `surface.json` (`research_surface.v1`) and contract validation (units, grids, arms, required columns, `cell_id` uniqueness, provenance/run consistency, linked runs resolve).
- [ ] 3.2 Setting `RESEARCH_SURFACES_ROOT`; discovery of `surface.json`; cached columnar loading of the cells table keyed by mtime and size.
- [ ] 3.3 Routes: surfaces list, surface definition, cells slice, geometry aggregates, findings; 404 and `surface_invalid` errors.
- [ ] 3.4 Tests on a small fixture surface with both grids and two arms, including aggregate values checked against a hand computation.

## 4. Migration of the EMA500 Surfaces

- [ ] 4.1 `scripts/surfaces/migrate_research_surface_v1.py`: write `surface.json`, back up `runs.csv`, add `cell_id`, `provenance`, `run_id`, `run_manifest_sha256`.
- [ ] 4.2 Ratio surface: link all 12 672 rows to their indexed bundles; report any row that does not resolve.
- [ ] 4.3 Trailing surface: link the Engine runs from `engine_runs.csv` and `engine_runs_parity_samples.csv` to matching replay rows (metrics within tolerance) or add them as `engine` rows; all other rows `replay`.
- [ ] 4.4 Idempotency check (second run byte-identical) and a validation report written next to each surface.

## 5. Surface Tab (research_frontend)

- [ ] 5.1 Types and API client for surfaces, cells slices, geometry aggregates, run reads with `manifest_sha256`.
- [ ] 5.2 `WorkbenchTab` `"surface"`, `TabNav` entry, tab outside `WorkbenchGate`.
- [ ] 5.3 Components: surface picker, heatmap, axis sliders with units and conversion, grid/metric/arm/comparison selectors, filmstrip, geometry map.
- [ ] 5.4 AND-filters with greyed cells, passing counter, "% cells passing filters" aggregate, persisted per browser.
- [ ] 5.5 Cell click: engine-linked cells select the run and open Chart; replay cells show the replay note; provenance marks.
- [ ] 5.6 Tests: vitest for slicing, unit conversion, filters and click handling; Playwright for engine-cell navigation and replay-cell note.

## 6. Verification and Rollout

- [ ] 6.1 Run the index against the local research data root and record totals, duplicates and conflicts.
- [ ] 6.2 Open a sample of historical ratio-surface cells end to end (cell → Chart → Reports).
- [ ] 6.3 Keep the static HTML visualisations as exports generated from the same surface contract.
