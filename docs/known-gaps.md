# Known cross-service gaps

Salvaged from the retired `38_recovery_gap_audit.md` (deleted 2026-08-26).
That doc's incident narrative (2026-07-15 recovery) is history and was
dropped; the items below were still open as of that doc and were not found
tracked anywhere else (README, master-plan.md, openspec/). Status not
re-verified during this docs cleanup — re-check against openspec/changes/
and src/ before acting on any item.

- MDS is intended to become the canonical owner of `market_data_hash`;
  Strategy Engine currently still computes it locally rather than accepting
  an MDS-supplied value.
- A separate MDS historical-backtest read endpoint (bypassing global
  readiness only after exact range/hash verification) was planned; runtime
  `/v1/candles` is meant to stay ready-only regardless.
- `research-history-window-planning-v1` (see `openspec/changes/`) covers the
  Research-side half of this; confirm current implementation status there
  rather than here.
