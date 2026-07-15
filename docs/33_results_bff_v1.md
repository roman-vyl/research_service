# Research results BFF v1

Step 14 of the function-porting plan exposes immutable run bundles through the Research Service BFF.

## Endpoints

- `GET /api/research/runs`
- `GET /api/research/runs/latest`
- `GET /api/research/runs/{run_id}`
- `GET /api/research/runs/{run_id}/summary`
- `GET /api/research/runs/{run_id}/trades`
- `GET /api/research/runs/{run_id}/metrics`

All endpoints read only `var/runs/<run_id>/` bundles produced by `research-run-artifacts-v1`. They never inspect legacy `research/results` directories.

`manifest.json` provides identity and creation ordering. Every referenced artifact is verified against its recorded byte size and SHA-256 before it is projected. `request.json`, `result.json`, and `metrics.json` provide the projections. Missing runs return `run_not_found`; malformed bundles return `invalid_run_artifact`.

Signal trace and chart-event projections are intentionally deferred to step 15.
