## Why

A starred candidate shows its strategy spec (the `strategy` of its Engine run) on
the Candidates tab, but the only way to hand that spec to Strategy Runtime is to
copy JSON by hand into the Runtime deployment catalog. The goal is a one-button
path from a candidate to Runtime, with the deployment arriving switched off; a
later change adds switching it on and watching it live.

Strategy Runtime reads its catalog from one flat directory
(`${BBB_DATA_ROOT}/strategy-runtime/specs`, mounted read-only into Runtime).
A deployment file is `{enabled, ticker, base_timeframe, strategy_id, raw_spec}`;
the run's `strategy` already has the last four fields, unchanged. The catalog is
re-read on every closed bar, so a new file needs no restart.

Whether a candidate is fit for Runtime is the owner's call, not Research's:
Research does not check the spec beyond the shape Runtime needs.

## What Changes

- New route `POST /api/research/candidates/{candidate_id}/runtime-export` writes
  the candidate's `strategy_spec_snapshot.spec` with `enabled: false` and a
  `research_source` block into the Runtime catalog directory as a new file. It
  never overwrites a file and refuses a spec whose Runtime identity is already in
  the catalog (Runtime drops every file of a duplicated identity).
- `GET /api/research/candidates` adds to `current` a `runtime` block: whether a
  catalog file with the candidate's Runtime identity exists, its file name and
  its `enabled` value, read from the directory at list time. Nothing about Runtime
  is stored in the candidate record.
- New setting `RESEARCH_RUNTIME_SPECS_PATH`; unset means export is unavailable
  (HTTP 503) and `current.runtime` is null.
- bbb_stack (separate PR): research-service gets
  `${BBB_DATA_ROOT}/strategy-runtime/specs` mounted read-write and the setting.
- research_frontend (separate OpenSpec): a "To Runtime" button on a candidate row.

## Out of scope

Switching `enabled`, Runtime read API, live view, Engine validation of the spec,
any check that the candidate is suitable for live trading, editing or deleting
catalog files, cleaning the current `loadtest-*` files. No change to Strategy
Engine or Strategy Runtime.
