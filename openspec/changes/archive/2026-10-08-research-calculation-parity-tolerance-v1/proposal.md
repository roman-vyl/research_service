## Why

The Calculate parity gate is a safeguard: it stops a recalculation from replacing a
row's stored result when the new Engine run does not reproduce it. Its float tolerance
(rel 1e-6) checks numeric identity, which stored Surfaces do not hold: their metrics
are stored at varying precision. On a 5-row smoke (35 cells) the trade counts matched
exactly while 29 float cells failed only on stored precision (largest relative
difference 7.9e-4).

## What Changes

- Integer metrics stay exact.
- Every other metric passes when
  `|actual − expected| ≤ max(abs_tolerance[field], 1e-3 × max(|actual|, |expected|))`.
- `abs_tolerance` is a fixed table per Engine summary field: `return_pct`, `win_rate`,
  `max_drawdown`, `profit_factor` 1e-4; `cumulative_net_r` 0.01; `net_pnl` 1.0. Other
  fields 1e-9. The field is the last segment of the result-binding path, so
  `long.net_pnl` uses the `net_pnl` floor.
- Nothing in the manifest: no profiles, no precision fields, no knowledge of how a
  table was written.

## Impact

- `adapters/experiments/run_calculation.py`: `REL_TOL = 1e-3`, `ABS_TOL` table,
  `_parity` receives the result bindings.
- Tolerance tests updated; the 35 smoke cells are a test fixture.
