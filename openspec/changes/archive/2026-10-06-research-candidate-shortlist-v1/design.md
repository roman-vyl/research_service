## Context

Facts from the code (`main` 5694bc4):

- `FilesystemExperiments` reads `analysis/experiments.json`, the manifest's
  `result_schema` and the result table, cached by `(path, mtime_ns, size)`, cache
  size 3 (`adapters/experiments/filesystem.py`). The analysis root is
  `artifacts_root.parent / "analysis"` (`runtime/settings.py`) and is writable by
  Research Service (task 1.1 of `research-run-deletion-v1`).
- A row has no own id. Its coordinates are the dimension values (for a multi-grid
  dimension, the column of the row's grid), `grid` and `arm` when declared.
  Uniqueness of coordinates is not guaranteed by the schema (older manifests have a
  `duplicate_rows` field).
- `run_id` is optional; run deletion clears it in place. Row indexes move when
  slices are appended or deleted.
- A run's strategy spec is `request.json` → `strategy` spec of that run, read with
  `FilesystemArtifactStore.read_run_file` (`GET /runs/{id}` surfaces it as
  `strategy_spec`).
- The manifest carries `varied_params` (column → label, unit, component id and
  param) and `fixed_params` (entry, ATR, sides, fees, sizing, initial equity).

## Decisions

### D1. The record is the selection

There is no `status` field. A record in `candidates.json` means the point is
picked by the user; unstar removes the record and the journal keeps the history.
A future deployment or runtime state is a separate entity that may reference
`candidate_id`; it is never stored in the shortlist record.

### D2. Candidate identity

The request carries `experiment_id` and `coords`, a map of semantic ids. The
required key set is exactly: every dimension id of the manifest, plus `grid` when
a dimension has grids, plus `arm` when `arms` is declared. Missing or extra keys
are HTTP 400 `invalid_coords`.

Canonical value: a numeric coordinate is parsed as float and written as
`format(x, ".12g")` with `-0` written as `0`; a text coordinate (`grid`, `arm`) is
kept as is. An empty coordinate (for example the grid and trigger of a
comparison-arm row) is `null` and matches only an empty cell. `candidate_id = "cand_" + sha256(canonical_json({"experiment_id",
"coords"}))[:24]`, where `canonical_json` is `json.dumps(sort_keys=True,
separators=(",", ":"))`. The backend alone builds it; the same point always gets
the same id.

### D3. Resolving a row

Rows are matched on all coordinates (numeric equality within `1e-9`, as the
results route filters). Zero rows: HTTP 404 `row_not_found`. More than one row:
HTTP 409 `ambiguous_row`; the service never picks one of them.

### D4. Row fingerprint

`fingerprint_fields` = every semantic id the results route serves for the row
except `run_id` and `provenance`: dimension ids (grid columns resolved by the
row's grid), `grid`, `arm`, every metric id, every `row_columns` name. The list is fixed
at star time and stored in the record.

Value canonicalization: empty cell → `null`; numeric → float → `format(x,
".12g")`; text as is. `fingerprint = "sha256:" + sha256(canonical_json({field:
value}))`. Columns not in `fingerprint_fields` (auxiliary columns, metrics added
to the manifest later) do not affect it; a field missing from the current schema
makes the row `changed`. `run_id` and `provenance` are excluded: they describe
the artifact behind the row (a run deleted or added, a replay point later run on
Engine), not the picked point itself, and are reported in `current`. A point
recalculated on Engine with different metrics is `changed` through its metrics.

### D5. Record

```json
{
  "candidate_id": "cand_…",
  "experiment_id": "btcusdt_p.ema500.ratio_4d",
  "coords": {"width": "9", "lookback": "60", "sl": "6", "tp_ratio": "7.5"},
  "picked_at": "2026-10-06T10:30:00Z",
  "fingerprint_fields": ["lookback", "max_drawdown_pct", "…"],
  "fingerprint": "sha256:…",
  "table_key": {"mtime_ns": 0, "size": 0},
  "snapshot": {
    "metrics": {"return_pct": 0.0, "profit_factor": 0.0, "…": 0},
    "provenance": "engine",
    "run_id": "run_…",
    "row_columns": {"market_data_hash": "…"}
  },
  "strategy_spec_snapshot": {"source": "run_request", "run_id": "run_…", "spec": {}}
}
```

`snapshot` holds values as the results route serves them. `strategy_spec_snapshot`
is `null` when the row has no `run_id`, or `{"source": null, "reason": …}` when
the run's `request.json` cannot be read; reading it never fails the star.

### D6. Strategy spec is a historical snapshot

The copied spec records what was picked. It is not kept in sync with the Surface,
and the shortlist never offers it as a deployable or executable specification. A
future deployment step defines its own check or materialization of an executable
spec; this change adds no seam that would send the snapshot anywhere.

### D7. Storage

`analysis/candidates.json` = `{"contract_version": "research_candidates.v1",
"candidates": [ … ]}`, ordered by `picked_at`. A missing file is an empty list. Each
write takes a process lock, writes `candidates.json.tmp-<pid>` and replaces the
file with `os.replace`, then appends one line to `candidates_journal.jsonl`
(`time_utc`, `action` star/unstar, the whole record). An unreadable file is HTTP
500 `invalid_candidates_file` and is never overwritten. One Research Service
process writes the file (as for run deletion).

### D8. Routes

- `GET /api/research/candidates` → `{"candidates": [record + "current"]}`.
- `PUT /api/research/candidates` body `{"experiment_id", "coords"}` → the record.
  Idempotent: if the candidate exists, the stored record is returned unchanged
  (the snapshot is not refreshed; to refresh, unstar and star again). Errors:
  404 unknown Experiment or `row_not_found`, 409 `ambiguous_row`, 400
  `invalid_coords`.
- `DELETE /api/research/candidates/{candidate_id}` → `{"removed": true|false}`;
  removing an absent candidate is not an error.

### D9. Current state on read

For each candidate the response adds:

```json
"current": {"row_state": "same|changed|missing|ambiguous",
            "run_id": "run_…" | null,
            "provenance": "engine" | "replay" | null,
            "metrics": { … } | null,
            "meaning": { … } | null}
```

- The table's `(mtime_ns, size)` equals `table_key`: `row_state = same`, current
  values are the snapshot, the table is not parsed.
- Otherwise the row is resolved by coordinates through the existing results cache:
  one row and equal fingerprint → `same`; one row, different fingerprint →
  `changed`; no row, or the Experiment is no longer registered or readable →
  `missing`; several rows → `ambiguous`. `run_id`, `provenance` and `metrics` come
  from the current row when there is one.
- `run_id` is the row's cell value; existence of the run folder is not checked
  (Open run reports a missing bundle, as today).
- `meaning` is built from the manifest: `title`, `ticker`, `anchor` from the
  registry; per coordinate `id`, `label`, `value`, `unit`, `component_id`,
  `component_param` (from the dimension and the matching `varied_params` entry by
  column); and `fixed_params` as stored in the manifest. `null` when the manifest
  is unreadable.

Cost: one read of `candidates.json`, one manifest read and one `stat` per
distinct Experiment, a table parse only when the table changed since the star.
No run folder is opened and no directory is listed on read; a star reads one
`request.json`.

## Risks

- Results cache holds 3 tables: with many changed tables a listing re-parses them.
  Acceptable for a shortlist of tens of candidates; measured in task 1.5.
- A manual edit of `candidates.json` while Research Service writes it may be lost;
  the journal keeps every change.
