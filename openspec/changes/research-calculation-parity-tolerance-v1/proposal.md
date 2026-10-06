## Why

The Calculate parity gate is a safeguard: it stops a recalculation from replacing a
row's stored result when the new Engine run does not reproduce it. Its float tolerance
(rel 1e-6) checks numeric identity, which stored Surfaces do not hold: legacy tables
store metrics rounded (4, 6 or 2 decimals depending on the builder). On the 5-row
smoke (35 cells) trade counts matched exactly and 29 float cells failed only from that
rounding; the largest relative difference was 7.9e-4 (cumulative R stored to 2
decimals).

## What Changes

- Integer metrics stay exact.
- Every other metric passes when
  `|actual − expected| ≤ max(1e-3 × max(|actual|, |expected|), 1e-6)`.
- Two fixed constants; nothing in the manifest, no per-Surface profiles, no
  knowledge of how a table was rounded.

## Impact

- `adapters/experiments/run_calculation.py`: `REL_TOL = 1e-3`, `ABS_TOL = 1e-6`.
- Tests of the tolerance boundary updated.
