## Context

Facts from the code (main at e8ed616):

- A run lives at `<artifacts_root>/<run_id>/`; `FilesystemArtifactStore.list_run_ids`
  lists directories there that pass the id pattern and contain `manifest.json`
  (skipping `batches` and dot-folders). `GET /api/research/runs` reads and verifies
  every listed run, so a half-deleted run in the root would break the list. A run is
  therefore deleted as a whole folder, never file by file.
- The Experiment API is read-only and reads `runs.csv` through a cache keyed by
  path, mtime and size (`adapters/experiments/filesystem.py`), so rewriting the table
  invalidates the cache without extra code.
- `result_schema.run_id_column` names the column holding the run id; a row without
  a run has an empty cell (nullable, already allowed by the contract).
- Provenance is declared by the manifest and never derived from `run_id`
  (`research-experiments-v1`), which is why clearing `run_id` loses nothing.

## Goals / Non-Goals

**Goals:** free the disk of selected runs; keep every metric and the Surface exactly
as it was; make the destructive step explicit, checkable and safe against stale
plans; keep run resolution and `GET /runs` untouched.

**Non-Goals:** see proposal.

## Decisions

### D1. Selection is a list of `run_id`

The frontend already has `run_id` for each cell from the results route. The request
names runs, not row keys, so there is no key-to-row mapping to get wrong.

### D2. Two routes

`POST /api/research/experiments/{experiment_id}/runs/delete-plan`

```json
{ "run_ids": ["run_..."] }
```

returns

```json
{
  "run_count": 47, "file_count": 376, "bytes": 8300000000,
  "already_absent": 0,
  "skipped": [{ "run_id": "run_...", "reason": "not_in_experiment" }],
  "plan_token": "sha256:..."
}
```

Nothing is changed. `POST .../runs/delete` takes `{ "run_ids": [...], "plan_token": "..." }`,
deletes as described below and returns the counts and the backup file name. The user's
confirmation (typing the planned run count) is a frontend step; the backend only checks
the token.

**Token.** SHA-256 over the sorted deletable run ids and the SHA-256 of the result
table. Its only job is to refuse a delete when the selection or the table is not what
the user was shown. If it differs the service changes nothing and answers 409
`plan_stale`. Stateless: nothing is stored on the server.

### D3. What is deletable

A requested `run_id` is deletable when all of these hold, else it is skipped with
the reason in brackets:

- it matches the run id pattern `run_` + 32 hex characters (`invalid_run_id`);
- it appears in the Experiment's result table, in `run_id_column` (`not_in_experiment`);
- no other registered Experiment's table references it (`shared_with_other_experiment`).
  The other tables are read only for this check.

A run that is referenced but whose folder is already missing is `already_absent`: it
costs 0 bytes and its `run_id` is still cleared.

### D4. Apply

Best-effort, safe to repeat. In this order:

1. Recompute the token; refuse with 409 `plan_stale` if it differs.
2. Copy `runs.csv` to `runs.pre_delete_<UTC>.csv`.
3. Delete each selected run folder whole (`rmtree`; a missing folder is not an error).
4. Write a new table to a temporary file in the same folder with the selected
   `run_id` cells emptied and every other cell byte-identical (read and written as
   plain strings), then rename it over `runs.csv`.
5. Append one line to `runs_deleted.jsonl` (UTC time, run ids, counts, bytes, backup name).

There is no transaction. If the process stops in the middle, some folders are gone
and `runs.csv` may still name them. That state is harmless and is repaired by
repeating the same delete: missing folders count as already deleted and their
`run_id` is cleared. A folder is removed in one operation, so the run list sees a run
either whole or not at all; nothing deletes files inside a run folder.

### D5. What is not touched

Every column other than `run_id`, the manifest, the registry, `findings.jsonl`,
other Experiments, `batches/`, and every run not selected. No new HTTP status for
reading a deleted run: its folder is gone, so the existing run routes answer 404
`RunNotFound`, and the frontend does not offer Open run for a row without `run_id`.

### D6. Concurrency with other writers

Scripts that write `runs.csv` (Engine fill, gap-fill) are not coordinated with this
service. The token covers a change between plan and apply; a script writing during the
apply itself is not covered. Deletion must not be run while such a script is writing the
same table; the frontend states this in the confirmation text.

### D7. Write access

Research Service already writes run bundles (`ensure_ready` writes a probe file in
`artifacts_root`), so `runs/` is writable. The analysis root is its sibling and has
been read-only in practice (the compose mount of `/data` is not checked from this
repository). The first task is to confirm that `/data/analysis` is writable in the
stack and, if not, change the mount; no code path depends on a new setting.

## Risks / Trade-offs

- Deletion is irreversible; the safeguards are the plan, the token, the typed
  confirmation in the frontend, the backup of the table and the journal. The deleted run itself is not
  recoverable except by recalculation (later change).
- A backup copy of the table per operation grows disk use by one table size
  (`runs.csv` of the trailing experiment is 53 MB). Old backups are removed by hand.
- Large selections (tens of thousands of runs) read file sizes of every run during
  the plan; the cost is a directory listing per run and is acceptable for the
  expected size, and is measured in the tasks.
