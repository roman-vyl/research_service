## Decisions

### D1. Source: the candidate's spec snapshot

The exported spec is `strategy_spec_snapshot.spec` of the record exactly as stored
at star time (the `strategy` of the run's `request.json`), the same JSON the
Candidates tab shows. A record whose snapshot has no `spec` (replay point,
unreadable `request.json`) is refused with 409 `no_strategy_spec`. Research does
not rebuild the spec from the manifest and does not look at the current row: the
owner decides what is exported (on 4 Engine-backed candidates the snapshot was
checked equal to a rebuild from `materialize`).

### D2. Create-only API and file content

The route takes only `candidate_id` in the path. It has no body and no query
parameters; any body field, including `enabled`, is rejected with 422. The file
always has `enabled: false`. There is no route to update, enable, disable or
delete a deployment file, and Research code never opens an existing catalog file
for writing.

```json
{
  "enabled": false,
  "strategy_id": "...", "ticker": "...", "base_timeframe": "...",
  "raw_spec": { ... },
  "research_source": {
    "candidate_id": "cand_...", "experiment_id": "...", "coords": {...},
    "run_id": "run_...", "exported_at": "2026-10-16T06:00:00Z"
  }
}
```

The four strategy fields are copied without change. Runtime accepts extra
top-level fields and leaves them out of identity; `research_source` is only for a
human reading the file. The snapshot's own `enabled`, if any, is replaced by
`false`. `strategy_instance_id`, `strategy_version` and `compatibility_profile`
are never written (Runtime rejects them).

### D3. Runtime identity is computed the Runtime way

Research computes the identity with the same formula as
`strategy_runtime/utility/deployment_catalog/identity.py`:
`strategy_id + ":" + sha256(json.dumps({strategy_id, ticker, base_timeframe,
raw_spec}, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
sort_keys=True))[:24]`. A unit test pins it against a fixed spec and the
expected id taken from Runtime. Only those four fields enter the formula, so
`enabled` and `research_source` do not affect it (tested). This is a copied
contract; if Runtime changes the formula, both must change together.

### D4. Catalog scan follows Runtime's rules

Research reads the directory the way `FilesystemDeploymentCatalog` does:
direct entries only, `is_file()`, name not starting with ".", suffix exactly
`.json`, JSON parsed with NaN and Infinity rejected. A file counts as a catalog
deployment only if Runtime would accept it: a JSON object without
`strategy_instance_id`, `strategy_version`, `compatibility_profile`; boolean
`enabled`; non-empty string `ticker`, `base_timeframe`, `strategy_id`; object
`raw_spec`. Its identity is then computed by D3. Any other file (unreadable, not
JSON, hidden, nested, uppercase suffix, rejected by those rules) is skipped and
can neither block an export nor count as a duplicate, because Runtime ignores it
too. If a file with the candidate's identity exists, export is 409
`runtime_duplicate` naming every such file and nothing is written. The files
Research writes pass the same acceptance rules (contract test, D9).

### D5. File name

`<slug>-<candidate_id>.json`. `slug` is the record's `ticker` lowercased with every
run of characters outside `[a-z0-9]` replaced by one `_` and leading/trailing `_`
removed (empty becomes `spec`), at most 40 characters. `candidate_id` is taken
from the stored record and must match `^cand_[0-9a-f]{24}$`; the path parameter is
only used to find the record and never enters the name. The resulting name has no
path separator, does not start with ".", and is at most 255 bytes; the resolved
parent of the final path must equal the resolved catalog directory, otherwise
export is 500 `runtime_invalid_name` and nothing is written.

### D6. Listing reads the directory, the record stays clean

`current.runtime` describes the directory only, not Runtime. It is computed on each
list from one scan (D4) and has these shapes:
`{"present": true, "file": name, "enabled": bool}` when exactly one accepted file has
the candidate's identity; `{"present": true, "duplicate": true, "files": [...]}`
when several have it (Runtime excludes all of them; `enabled` is not reported);
`{"present": false}` when none has; `null` when the setting is unset, the
directory is unreadable or the record has no spec. It does not say that Runtime
loaded the file, selected it, or executes the strategy. The candidate record and
`candidates.json` get no Runtime field, so the rule "a record carries no
deployment field" holds. On a successful export one journal line `runtime_export`
is appended to `candidates_journal.jsonl`.

### D7. Configuration

`RESEARCH_RUNTIME_SPECS_PATH` (optional). Unset: export is 503
`runtime_catalog_unconfigured`. Set but missing or not a directory: export is 503
`runtime_catalog_unavailable`; Research never creates the directory.

### D8. Concurrency

The sequence scan → duplicate check → publish runs under an exclusive
`fcntl.flock` on `<analysis>/.runtime_export.lock` (Research's own storage, not the
catalog directory), plus a process-local `threading.Lock`. The order is lock → scan →
duplicate check → publish → journal attempt → unlock; the journal attempt runs
inside the lock (a failure there follows D9). A second export waits, then sees the first file in its scan.
Two candidates with the same Runtime identity therefore produce exactly one file
and one `runtime_duplicate`. Waiting is bounded (10 s, then 503
`runtime_export_busy`).

Boundary of the guarantee: it holds among Research processes that share the lock
file's filesystem and kernel (workers of one service; one host). It does not cover
a writer outside Research (a person, a script, another service) that creates a
file with the same identity between the scan and the publish. In that case Runtime
excludes both files, which is fail-closed (neither trades), and `current.runtime`
shows `duplicate: true` with both names. The final name itself is still never
overwritten, because publication is an exclusive create.

### D9. Filesystem failures

Write: content goes to a hidden temporary file `.<name>.tmp-<pid>-<random>` in the
catalog directory (Runtime's scan ignores it), is flushed and fsynced. Publish:
`os.link(tmp, final)` (fails if `final` exists), then fsync of the directory, then
unlink of the temporary file. The temporary file is unlinked in a `finally` on
every path.

- Temporary file cannot be created or written (disk full, permission, read-only
  mount): 500 `runtime_write_failed`, nothing published, partial temporary file
  removed.
- Final name exists: 409 `runtime_file_exists`, existing file untouched.
- Link fails for another reason (including a filesystem without hard links): 500
  `runtime_publish_failed`, nothing published. No fallback to a non-atomic write.
- Directory fsync fails after a successful `os.link`: the file counts as published; the
  error is logged with the file name and the export still succeeds.
- Unlink of the temporary file fails after a successful publish: the export still
  succeeds and the error is logged; a hidden leftover is ignored by Runtime and
  Research never deletes other files.
- Existing files are never opened for writing, renamed or deleted. Temporary
  files of a crashed earlier process are left in place (hidden, harmless).
- Journal write fails after the file is published: the export is reported as
  success (201) with `journal: "failed"` and the error logged. The file is not
  rolled back, since Research does not delete deployments. A repeated press then
  answers 409 `runtime_duplicate` with the file name, which is true, so the owner
  is never told that nothing was exported.

### D10. Access

The route has no authentication of its own: it follows the existing Research API
access model (CORS only). Before deployment the stack must be checked so that the
route is reachable only through the same protected path as the rest of the Research
API (port binding, proxy), and the result recorded in tasks 2.2. The read-write
mount gives the container write capability on the catalog directory beyond the
API; the code only ever creates new files there (D2, D9), and this is covered by a
test that compares every pre-existing file (bytes and mtime) before and after exports.
