## 1. Backend (research_service)

- [x] 1.1 Setting `runtime_specs_path` (`RESEARCH_RUNTIME_SPECS_PATH`), optional.
- [x] 1.2 Runtime identity function (D3) with a pinned test against an id produced by Strategy Runtime; test that `research_source` and `enabled` do not change it.
- [x] 1.3 Catalog scan (D4) with Runtime's file selection and acceptance rules; identity per accepted file, others skipped.
- [x] 1.4 Safe file name (D5) and its checks.
- [x] 1.5 Inter-process lock (D8): `flock` on `<analysis>/.runtime_export.lock` plus a thread lock, 10 s bound.
- [x] 1.6 `POST /api/research/candidates/{candidate_id}/runtime-export`, no body, forced `enabled: false`: 404 unknown candidate, 409 `no_strategy_spec` / `runtime_duplicate` / `runtime_file_exists`, 422 for any body, 500 `runtime_write_failed` / `runtime_publish_failed` / `runtime_invalid_name`, 503 unconfigured / unavailable / busy; temp file, link, fsync, cleanup (D9); journal line; `journal: "failed"` on journal error.
- [x] 1.7 `current.runtime` in the list (D6), including the duplicate shape.
- [x] 1.8 Tests, content: four fields unchanged, `enabled` false, `research_source`, no forbidden fields; file accepted by a copy of Runtime's acceptance rules; `candidates.json` byte-identical after export.
- [x] 1.9 Tests, catalog: repeat export 409; hand-made file with the same identity in other formatting 409; invalid JSON, hidden, nested, `.JSON`, Runtime-rejected files do not block an unrelated candidate; a Runtime-rejected file with the same four fields does not count as duplicate.
- [x] 1.10 Tests, concurrency: two processes export different candidates with one Runtime identity at once (exactly one file, one 409); two different identities at once (both complete); external same-identity file after the scan (no overwrite, list shows `duplicate`).
- [x] 1.11 Tests, failures: out-of-space on write, link refused, final name exists, temp unlink failure after publish, journal failure after publish (201 with `journal: "failed"`, then 409), no temp file left in each failing case; existing files unchanged in bytes and mtime.
- [x] 1.12 Tests, file name: hostile tickers (`../`, `/abs`, leading ".", control and non-ASCII characters, 300 characters), malformed `candidate_id` in a stored record; nothing written outside the directory.
- [x] 1.13 Tests, API surface: body with `enabled` is 422; no other route writes to the catalog directory; unset path gives 503 and the list still works.

## 2. Stack (bbb_stack, separate PR)

- [ ] 2.1 research-service: bind `${BBB_DATA_ROOT}/strategy-runtime/specs` read-write at `/runtime-specs`, `RESEARCH_RUNTIME_SPECS_PATH=/runtime-specs`. Runtime's own mount stays read-only.
- [ ] 2.2 Before deployment, check and record that the Research API (including this route) is reachable only through the existing protected path (port binding / proxy), and that `flock` and hard links work on the bind-mounted directory on the Mac.

## 3. Frontend (research_frontend, separate OpenSpec)

- [ ] 3.1 "To Runtime" button on a candidate row (see `research-workbench-candidate-runtime-export-v1`); wording of the mark follows D6.

## 4. Verification

- [ ] 4.1 Owner check on the Mac: export one candidate; the file appears with `enabled: false`; Runtime's catalog accepts it (no `invalid_files`, not selected); second press says it is already there.
