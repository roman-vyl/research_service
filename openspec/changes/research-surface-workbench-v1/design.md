## Context

See `proposal.md`. Facts the design relies on (checked 2026-10-03 on the local
research data root `BBB_data/research`):

- Primary artifacts root (`settings.artifacts_root`, here `BBB_data/research/runs`):
  32 990 flat run bundles `<root>/<run_id>/manifest.json`; batch outputs in
  `<root>/batches/<experiment_id>/{manifest,request,summary}.json` whose
  candidate `artifact_path` values are container paths (`/data/runs/run_…`),
  not host paths.
- Canonical research folders under `BBB_data/research/analysis/<ticker>/<anchor>/<test>/`:
  copied run bundles at `runs/<batch_id>/candidates/<run_id>/` (26 659), plus
  other analysis run copies (19 193 paths, 6 297 of them reachable only via
  symlinks created when folders were reorganised).
- Run ids follow `run_[0-9a-f]{32}` (`_SAFE_ID_RE` in
  `adapters/artifacts/filesystem.py`).
- `ReadResearchRuns` reads through `RunArtifactReader.read_run_file(run_id, name)`
  and verifies manifest hashes in `_documents()`.
- Frontend selection is a single `selectedRunId` in `WorkbenchContext`; report
  and chart data load from `/api/research/runs/{run_id}*`.

## Goals / Non-Goals

**Goals**

- Open any existing run by `run_id` regardless of where its bundle lives, with
  no copying and an exact, verifiable identity.
- Serve surfaces from the folders where they already live.
- One surface cell maps to at most one run; replay rows are labelled as such.
- Units of every axis are explicit in the contract and in the UI.

**Non-Goals**

- Materializing runs for replay cells, deleting copies, changing `/runs` list
  scope (see proposal).

## Decisions

### D1. Run index: discovery, identity, precedence

- Roots: `artifacts_root` (primary, rank 0) followed by
  `RESEARCH_RUN_INDEX_EXTRA_ROOTS` (ordered list, rank 1..n). Extra roots are
  read-only to Research Service.
- Discovery: any directory named `run_<32 hex>` that contains `manifest.json`,
  at any depth under a root, following symlinks. The `batches/` subtree of the
  primary root is scanned too (it contains no run bundles today but may later).
- Each discovered location is canonicalised with `realpath`; locations that
  resolve to the same real directory are one copy.
- Identity of a copy: `(run_id, manifest_sha256)` where `manifest_sha256` is
  the SHA-256 of the `manifest.json` bytes. Because the manifest lists every
  other file with its SHA-256, equal manifest hashes mean equal bundles.
- Resolution of a bare `run_id`:
  - one distinct `manifest_sha256` among all copies → resolved; the copy with
    the lowest root rank, then the lexicographically smallest real path, is the
    read location; all other locations are recorded as `duplicates`;
  - more than one distinct `manifest_sha256` → `ambiguous`; bare-id reads fail
    with HTTP 409 `run_ambiguous`. A caller may pass `manifest_sha256` to pick
    one copy exactly.
- Manifest hash verification on read stays as today; the index never
  substitutes for it.

Alternatives considered: importing (copying or hard-linking) all bundles into
`artifacts_root` was rejected by the owner (no copying, 22+ GB, double
bookkeeping). Trusting batch `artifact_path` was rejected because those are
container paths.

### D2. Index lifecycle

- Built on service start in the background; readiness reports
  `run_index: building | ready | failed` with counts. Read routes for runs in
  the primary root keep working while it builds; lookups that need an extra
  root return HTTP 503 `run_index_building` until ready.
- Persisted snapshot at `<artifacts_root>/.run_index/index.jsonl` (one line per
  copy: `run_id`, `manifest_sha256`, `root_rank`, `real_path`,
  `manifest_mtime_ns`, `manifest_size`) so restarts are fast; a root is rescanned
  when its directory mtimes changed, and on `POST /api/research/run-index/refresh`.
- `GET /api/research/run-index` returns totals, per-root counts, duplicate and
  conflict counts, and the list of ambiguous run ids.
- New bundles published through the normal path are added to the index at
  publish time.

### D3. Surface contract `research_surface.v1`

A surface is an existing canonical test folder plus a new `surface.json`:

- `contract_version: "research_surface.v1"`, `surface_id`, `title`.
- `market`: `ticker`, `timeframe`, `from_ms`, `to_ms`, `market_data_hash`.
- `cells_table`: relative path (default `runs.csv`) and its column mapping.
- `axes`: ordered list; each axis has `column`, `label`, `unit`
  (`ATR`, `R`, `bars`, …), and either explicit `values` or `discover: true`.
  Grid-dependent axes (trailing T/D) declare `grids`, each with its unit and
  the columns that hold the value in that unit, plus a `grid_column`
  (`geometry_grid_unit`).
- `arms`: arm ids present in the `arm` column, their role
  (`treatment` | `comparison`), and which comparison arm is the matched
  baseline (`control_tp5r`).
- `metrics`: column, label, unit, and display scaling (`return_pct` and
  `max_drawdown_pct` are fractions).
- `findings`: relative path of `findings.jsonl` (optional).

Required cell columns: `cell_id`, `arm`, every axis column, `provenance`,
`run_id` (may be empty), `run_manifest_sha256` (empty when `run_id` is empty).

`cell_id` = `"cell_" + first 24 hex of SHA-256(canonical JSON)` of
`{surface_market_data_hash, arm, axis values in their declared units}`. It is
stable across regenerations of the same surface and unique within a surface.
(A cross-surface strategy-spec hash was considered; it needs the full spec per
replay row, which does not exist, so it is out of scope.)

`provenance`:
- `engine`: the row's metrics come from the referenced Engine run;
- `engine_confirmed_replay`: replay row whose run was also executed by Engine
  and matched (the run is linked);
- `replay`: replay row, no run.

### D4. Surfaces API (read-only)

- `GET /api/research/surfaces` → `[{surface_id, title, ticker, timeframe, anchor, row_count, arms, axes}]`
  from every `surface.json` under `RESEARCH_SURFACES_ROOT`.
- `GET /api/research/surfaces/{surface_id}` → the `surface.json` content plus
  discovered axis values.
- `GET /api/research/surfaces/{surface_id}/cells` with axis filters as query
  parameters (`sl_atr_multiplier=5&geometry_grid_unit=R&trigger_r=7&trail_distance_r=0.5`)
  and `arm` (repeatable) → columnar JSON
  `{columns: [...], rows: [[...], ...]}` limited to the requested slice.
- `GET /api/research/surfaces/{surface_id}/geometry-aggregates?sl_atr_multiplier=…&grid=…&comparison_arm=…`
  → per (T, D) aggregates against the comparison arm (median Δ net, median
  multiple on profitable comparison cells, share better on net+PF+DD, median
  Δ PF, median Δ DD, median Δ R, median net).
- `GET /api/research/surfaces/{surface_id}/findings` → findings lines.
- The cells table is loaded once per surface and cached keyed by file mtime and
  size; malformed tables return a stable 500 `surface_invalid` naming the
  violation.

### D5. Frontend Surface tab

- `WorkbenchTab` gains `"surface"`; `TabNav` adds "Surface". The tab is outside
  `WorkbenchGate` (it does not need a selected run).
- Port of the verified HTML behaviour: surface picker; SL / T / D sliders whose
  readout always shows the unit and the conversion to the other unit at the
  selected SL; grid switch (ATR / R); metric and arm toggles; comparison arm
  selector; AND-filters on metrics and comparison deltas (failing cells grey);
  T filmstrip; T × D geometry map with aggregates including "% cells passing
  filters".
- Cell click:
  - `run_id` present → `setSelectedRunId(run_id)` (passing
    `run_manifest_sha256` through the API as a qualifier) and switch to Chart;
  - `provenance=replay` → an inline panel "replay result, no Engine run yet"
    with the cell's coordinates and metrics; no navigation.
- Each cell shows a provenance mark; the tooltip lists both units of T and D.

### D6. Migration of existing surfaces

`scripts/surfaces/migrate_research_surface_v1.py` (Research Service repo,
offline, idempotent):
- writes `surface.json` for the two EMA500 surfaces;
- backs up `runs.csv` as `runs.pre_surface_v1.csv`, then adds `cell_id`,
  `provenance`, `run_id`, `run_manifest_sha256`;
- historical ratio surface: `provenance=engine`, `run_id` from the existing
  column, `run_manifest_sha256` from the bundle found through the index;
- trailing surface: `provenance=replay` except rows matched to the 415 Engine
  runs in `engine_runs.csv` / `engine_runs_parity_samples.csv`
  (`engine_confirmed_replay`, linked); rows of those Engine runs that lie
  outside the replay grid are appended with `provenance=engine`;
- validates uniqueness of `cell_id`, that every linked run resolves in the
  index, and that linked metrics match the run's `metrics.json` within
  tolerance.

## Risks / Trade-offs

- Scanning ~80 000 bundle directories on start: mitigated by the persisted
  snapshot and mtime-based rescans; reads of primary-root runs never wait.
- Extra roots are mutable outside the service: the index can be stale between
  refreshes; reads still verify manifests and a missing file yields 404, not
  wrong data.
- `runs.csv` of the trailing surface is 51 MB; served only as slices.
- A future second copy with a different manifest makes a bare run id
  ambiguous; the 409 and the index report make it visible instead of silently
  choosing.

## Open Questions

- None blocking. Cleanup policy for unreferenced copies will be decided from
  the index report after rollout.
