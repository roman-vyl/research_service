# Research diagnostics projection v1 specification

## Requirements

1. Research Service SHALL expose signal-trace and chart-events for immutable new-format runs.
2. The projection SHALL use Strategy Engine component evidence as the source of strategy semantics.
3. The projection SHALL use Research execution events as the source of fill and lifecycle facts.
4. The projection SHALL NOT call MDS or Strategy Engine at read time.
5. The projection SHALL NOT import or execute `legacy_source`.
6. Dense arrays SHALL remain aligned to the requested market-grid slice.
7. `portfolio_entry` SHALL equal strategy entry gated by `stop_ready`.
8. Unknown single-run variants and context overlay references SHALL return stable invalid-request errors.
