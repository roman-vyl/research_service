# Tasks

- [x] Add immutable static exit candidate, arbitration and fill contracts.
- [x] Consume initial stop/take levels without recalculating strategy policy.
- [x] Consume aligned Strategy Engine signal-exit series.
- [x] Preserve long/short gap-through and intrabar touch semantics.
- [x] Preserve signal exit at bar close.
- [x] Preserve same-bar priority `stop_loss -> take_profit -> signal`.
- [x] Prevent exit processing on the entry bar.
- [x] Preserve losing candidates for diagnostics.
- [x] Add reviewed acceptance scenarios without executing legacy source.
- [ ] Merge static and managed candidates in `research-unified-execution-loop-v1`.
