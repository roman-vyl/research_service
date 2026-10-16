## Decisions

### D1. Source: the candidate's spec snapshot

The exported spec is `strategy_spec_snapshot.spec` of the record exactly as stored
at star time (the `strategy` of the run's `request.json`), the same JSON the
Candidates tab shows. A record whose snapshot has no `spec` (replay point,
unreadable `request.json`) is refused with 409 `no_strategy_spec`. Research does
not rebuild the spec from the manifest and does not look at the current row: the
owner decides what is exported (on 4 Engine-backed candidates the snapshot was
checked equal to a rebuild from `materialize`).

### D2. File content

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
expected id taken from Runtime. This is a copied contract; if Runtime changes
the formula, both must change together.

### D4. Duplicates and overwrite

Before writing, Research reads every direct, visible, lowercase `.json` file of
the directory (the same set Runtime scans), parses it, and computes its identity
from its four fields. Files that do not parse or lack the fields are skipped for
this check. If any file has the candidate's identity, export is 409
`runtime_duplicate` with that file name and nothing is written. Repeating export
of the same candidate therefore returns 409, not a second file.

### D5. File name and atomic write

Name: `<ticker lowercased, "." → "_">-<candidate_id>.json`, e.g.
`btcusdt_p-cand_edb786ef6040a0454f1b4710.json`. The content is written to a hidden
temporary file in the same directory (`.<name>.tmp-<pid>`, ignored by Runtime's
scan), flushed, then linked to the final name with an exclusive create
(`os.link`, fails if the name exists), then the temporary file is removed. An
existing name is 409 `runtime_file_exists`. Runtime never sees a half-written file.

### D6. Listing reads the directory, the record stays clean

`current.runtime` is computed on each list: one directory scan, then identities
of the files (D4). `{"present": true, "file": name, "enabled": bool}` when a file
with the candidate's identity exists, `{"present": false}` otherwise, `null`
when the setting is unset, the directory is unreadable, or the record has no
spec. The candidate record and `candidates.json` get no Runtime field, so the
rule "a record carries no deployment field" holds. One journal line
`runtime_export` is appended to `candidates_journal.jsonl` on a successful export.

### D7. Configuration

`RESEARCH_RUNTIME_SPECS_PATH` (optional). Unset: export is 503
`runtime_catalog_unconfigured`. Set but missing or not a directory: export is 503
`runtime_catalog_unavailable`; Research never creates the directory.
