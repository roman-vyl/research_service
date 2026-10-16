## 1. Backend (research_service)

- [ ] 1.1 Setting `runtime_specs_path` (`RESEARCH_RUNTIME_SPECS_PATH`), optional.
- [ ] 1.2 Runtime identity function (D3) with a pinned test against an id produced by Strategy Runtime.
- [ ] 1.3 Catalog scan (D4): direct visible lowercase `.json` files, identity per parsable file, unparsable skipped.
- [ ] 1.4 `POST /api/research/candidates/{candidate_id}/runtime-export`: 404 unknown candidate, 409 `no_strategy_spec`, 409 `runtime_duplicate`, 409 `runtime_file_exists`, 503 unconfigured/unavailable; atomic exclusive write (D5); journal line.
- [ ] 1.5 `current.runtime` in the list (D6).
- [ ] 1.6 Tests: file content (four fields unchanged, `enabled` false, `research_source`, no forbidden fields); repeat export 409; a hand-made file with the same identity but other formatting → 409; unparsable file in the directory does not block; unset path 503; list shows `present`/`enabled` and null without the setting; `candidates.json` unchanged by export.

## 2. Stack (bbb_stack, separate PR)

- [ ] 2.1 research-service: bind `${BBB_DATA_ROOT}/strategy-runtime/specs` read-write at `/runtime-specs`, `RESEARCH_RUNTIME_SPECS_PATH=/runtime-specs`. Runtime's own mount stays read-only.

## 3. Frontend (research_frontend, separate OpenSpec)

- [ ] 3.1 "To Runtime" button on a candidate row (see `research-workbench-candidate-runtime-export-v1`).

## 4. Verification

- [ ] 4.1 Owner check on the Mac: export one candidate; the file appears with `enabled: false`; Runtime's catalog accepts it (no `invalid_files`, not selected); second press says it is already there.
