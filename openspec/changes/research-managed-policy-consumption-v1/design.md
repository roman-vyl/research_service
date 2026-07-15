# Design

## Boundary

Strategy Engine owns policy evaluation. Research Service owns market execution.

## Flow

1. Validate replay identity against `PositionState`.
2. Replay policy events only to retain rule/component attribution.
3. Shift each bar decision to `effective_from_time_ms`.
4. Create a `ManagedEffectiveState` for the executable bar.
5. On that bar, detect managed-stop hits and emit runtime-exit candidates.

## Compatibility

Candidate classes and gap semantics mirror the legacy BBB execution path. The unified same-bar priority is deliberately deferred to the next change.
