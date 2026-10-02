## Why

Research currently interprets every historical managed `stop_action.distance_id` as an absolute offset from entry, which cannot represent an MFE-following trailing stop or an initial-R lock without leaking strategy components and raw parameters across the Engine boundary. Engine will now project a closed stop execution formula, while Research already owns the frozen initial risk and monotonic best price needed to execute it generically.

## What Changes

- Extend the Research decode of `ManagedStopActionRule` with the closed formulas `entry_offset`, `initial_r_lock`, and `initial_r_trailing`, plus opaque trigger/distance references.
- Preserve the legacy contract: omitted `stop_formula` means `entry_offset`, and existing projection documents remain valid.
- Execute initial-R trigger, fixed lock, and MFE-following trailing candidates from position-local frozen `initial_risk` and monotonic MFE, without inspecting `component_id` or raw strategy parameters.
- Reuse existing tighten-only arbitration, attribution stability, next-bar-effective state, managed stop hit handling, and unified exit arbitration.
- Keep eager timeline and incremental execution formula-for-formula equivalent and fail closed when initial risk is unavailable or invalid.
- Add DTO validation, compatibility, parity, timing, long/short, monotonic-ratchet, and end-to-end execution coverage.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `research-managed-policy-consumption-v1`: decode and execute the closed initial-R lock/trailing stop formulas while preserving legacy entry-offset behavior and strategy/execution ownership boundaries.
- `research-historical-execution-parity-v1`: require end-to-end parity coverage for the new stop formulas through the production historical execution path.

## Impact

- Historical managed projection DTOs and reference validation.
- Eager managed-policy timeline and incremental managed trade state advancement.
- Managed stop event attribution and existing unified exit execution tests.
- Coordinated Strategy Engine change `initial-r-stop-management-v1` supplies the new projection fields; no new Research-to-Engine request pattern is introduced.
