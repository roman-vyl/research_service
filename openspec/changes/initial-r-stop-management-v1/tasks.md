## 1. Projection DTO and Compatibility

- [x] 1.1 Extend the stop-action DTO with the closed formula enum, legacy `entry_offset` default, and optional opaque trigger-distance reference.
- [x] 1.2 Enforce formula-specific field invariants and include trigger references in projection dangling-reference validation.
- [x] 1.3 Add contract tests for legacy payload decode, every valid formula, unknown formulas, invalid trigger presence/absence, and dangling references.
- [x] 1.4 Add a cross-repository fixture proving new Engine output decodes without `component_id` or named strategy parameters.

## 2. Shared Stop Candidate Execution

- [x] 2.1 Implement one generic stop-candidate helper for entry-offset, initial-R lock, and initial-R trailing formulas.
- [x] 2.2 Route both eager timeline construction and incremental state advancement through the helper while retaining the existing `_tightened_stop` arbitration.
- [x] 2.3 Preserve frozen initial risk through every incremental state transition and treat missing/non-positive risk and unavailable/non-finite distances as no candidate.
- [x] 2.4 Add long/short formula tests for 6R-to-4R locking, the 6R/7R/8R/11.5R trail, different risks sharing one projection, retracement, and competing stops.

## 3. Timing, Events, and Execution

- [x] 3.1 Add eager/incremental bar-for-bar parity coverage containing both new stop formulas.
- [x] 3.2 Prove non-tightening candidates retain the active rule id and emit no active-stop update.
- [x] 3.3 Prove a source-bar trigger becomes effective only at `next_time_ms` and cannot execute on its source candle.
- [x] 3.4 Add production-loop tests showing repeated trail advances execute at the latest effective stop through existing managed-stop and unified-exit arbitration.
- [x] 3.5 Verify legacy entry-offset stop, managed-stop fill, partial-take, event, and arbitration fixtures remain unchanged.

## 4. Historical Production Parity

- [x] 4.1 Add end-to-end historical runs for initial-R lock and trailing exits, including fills, rule attribution, trade records, and aggregate results.
- [x] 4.2 Prove multi-trade candidates continue to use one candidate-wide projection with zero per-trade managed-replay HTTP calls.
- [x] 4.3 Exercise both new formulas through persisted execution and managed-policy event artifacts where those artifacts already record the affected state.

## 5. Verification and Cross-Repository Handoff

- [x] 5.1 Run focused DTO, managed-policy, incremental parity, projection-loop, unified-exit, event, and artifact test suites.
- [x] 5.2 Run the full Research test and static-quality gates and record any unrelated pre-existing failures separately.
- [x] 5.3 Verify legacy and new fixtures against the coordinated Engine serializer and confirm Research-first deployment compatibility.
- [x] 5.4 Run `openspec validate initial-r-stop-management-v1 --strict` and reconcile proposal, specs, design, and completed tasks before implementation handoff.

Verification evidence: 579 tests passed; Ruff and mypy passed. Legacy stop-action
serialization omits the new fields, while both initial-R formulas decode from the
coordinated Engine wire shape before the Engine producer is deployed.
