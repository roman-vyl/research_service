# Tasks

- [x] Add execution-loop result and event contracts.
- [x] Add the single-instance bar-by-bar state machine.
- [x] Preserve exit-before-entry ordering.
- [x] Preserve no exit on the entry bar.
- [x] Preserve no replacement entry on a bar that began with an open position.
- [x] Resolve managed replay once per opened position.
- [x] Apply managed state only at `effective_from_time_ms`.
- [x] Preserve unclosed positions without a synthetic exit fill.
- [x] Add static, managed, re-entry, open-position and invalid-identity tests.
- [x] Update the function-porting and master plans.
- [ ] Add fees, PnL and trade accounting in `research-trade-accounting-v1`.
