## 1. Projection DTO and Compatibility

- [ ] 1.1 Extend the stop-action DTO with the closed formula enum, legacy `entry_offset` default, and optional opaque trigger-distance reference.
- [ ] 1.2 Enforce formula-specific field invariants and include trigger references in projection dangling-reference validation.
- [ ] 1.3 Add contract tests for legacy payload decode, every valid formula, unknown formulas, invalid trigger presence/absence, and dangling references.
- [ ] 1.4 Add a cross-repository fixture proving new Engine output decodes without `component_id` or named strategy parameters.

## 2. Shared Stop Candidate Execution

- [ ] 2.1 Implement one generic stop-candidate helper for entry-offset, initial-R lock, and initial-R trailing formulas.
- [ ] 2.2 Route both eager timeline construction and incremental state advancement through the helper while retaining the existing `_tightened_stop` arbitration.
- [ ] 2.3 Preserve frozen initial risk through every incremental state transition and treat missing/non-positive risk and unavailable/non-finite distances as no candidate.
- [ ] 2.4 Add long/short formula tests for 6R-to-4R locking, the 6R/7R/8R/11.5R trail, different risks sharing one projection, retracement, and competing stops.

## 3. Timing, Events, and Execution

- [ ] 3.1 Add eager/incremental bar-for-bar parity coverage containing both new stop formulas.
- [ ] 3.2 Prove non-tightening candidates retain the active rule id and emit no active-stop update.
- [ ] 3.3 Prove a source-bar trigger becomes effective only at `next_time_ms` and cannot execute on its source candle.
- [ ] 3.4 Add production-loop tests showing repeated trail advances execute at the latest effective stop through existing managed-stop and unified-exit arbitration.
- [ ] 3.5 Verify legacy entry-offset stop, managed-stop fill, partial-take, event, and arbitration fixtures remain unchanged.

## 4. Historical Production Parity

- [ ] 4.1 Add end-to-end historical runs for initial-R lock and trailing exits, including fills, rule attribution, trade records, and aggregate results.
- [ ] 4.2 Prove multi-trade candidates continue to use one candidate-wide projection with zero per-trade managed-replay HTTP calls.
- [ ] 4.3 Exercise both new formulas through persisted execution and managed-policy event artifacts where those artifacts already record the affected state.

## 5. Verification and Cross-Repository Handoff

- [ ] 5.1 Run focused DTO, managed-policy, incremental parity, projection-loop, unified-exit, event, and artifact test suites.
- [ ] 5.2 Run the full Research test and static-quality gates and record any unrelated pre-existing failures separately.
- [ ] 5.3 Verify legacy and new fixtures against the coordinated Engine serializer and confirm Research-first deployment compatibility.
- [ ] 5.4 Run `openspec validate initial-r-stop-management-v1 --strict` and reconcile proposal, specs, design, and completed tasks before implementation handoff.
