## 1. Consumption

- [ ] 1.1 `ManagedStopActionRuleDTO.stop_basis` (optional, strict enum).
- [ ] 1.2 Candidate by `stop_basis` in the eager builder and the
      incremental advance, from frozen `initial_risk` and the running
      best price; discard when not tighter than the initial stop or
      without initial risk. Verify: long/short lock and trail tests,
      eager vs incremental parity, no initial stop.
- [ ] 1.3 Execution: a trail stop exits at its level through the
      existing managed-stop path; `stop_loss` keeps priority on a
      shared bar. Verify: loop-level test.

## 2. Gate

- [ ] 2.1 `make verify` green; existing no-basis outputs unchanged.
- [ ] 2.2 `openspec validate initial-r-stop-management-v1 --strict`.
