## Why

Strategy Engine adds `r_stop` (`initial-r-stop-management-v1`): a stop
measured in the trade's initial R, as a fixed lock (`stop_R = lock_r`)
or a trail (`stop_R = MFE_R - trail_r`). Engine projects it as a
`stop_action` rule with a new optional `stop_basis`. Research must
compute the candidate from its own entry, initial risk and best price,
because those are per-trade facts the per-bar distance series cannot
carry.

## What Changes

- `ManagedStopActionRuleDTO` accepts optional
  `stop_basis: "lock_r" | "trail_r"`.
- The eager timeline builder and the incremental advance compute:
  - no basis: `entry ± distance` (unchanged);
  - `lock_r`: `entry ± distance × initial_risk`;
  - `trail_r`: `mfe_price ∓ distance × initial_risk`;
  and discard an R-based candidate that is not tighter than the initial
  stop or has no initial risk.
- Ratchet, next-bar effectiveness, same-bar arbitration and the managed
  stop level fill are unchanged.

## Impact

- `research-managed-policy-consumption-v1`: ADDED R-based stop actions.
- No change for projections without `stop_basis`.
