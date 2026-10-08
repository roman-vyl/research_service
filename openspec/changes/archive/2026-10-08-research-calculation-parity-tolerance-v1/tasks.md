## 1. Implementation

- [x] 1.1 Gate: integers exact; other metrics `|a − e| ≤ max(ABS_TOL[field], 1e-3 × max(|a|, |e|))` with the fixed field table; `_parity` gets the result bindings.
- [x] 1.2 Tests: the 35 smoke cells pass; a 0.2 % change fails; floors near zero for `return_pct`, `net_pnl`, `cumulative_net_r`; side path `long.net_pnl` uses the `net_pnl` floor; trade count off by one fails.
- [x] 1.3 `make verify` and `openspec validate --all --strict` (1.7.0).

## 2. Verification on the Mac (on command)

- [x] 2.1 Deploy, then Calculate the 5 rows of `btcusdt_p.ema500.calc_smoke_width_band` again; report how many pass.
  - 2026-10-08: research-service dac0f91 deployed on the Mac (8095). The 5 rows were calculated from the Workbench UI (job `calc_1dffb5af…`): 5 published, 0 parity failed, backup `runs.pre_calculate_20261008T173929Z.csv`. Trade counts are equal (212/269/336/392/411). The continuous metrics differ only by the stored 4-digit rounding, which is within the tolerances, and full-precision Engine values replaced them on publish. The test Experiment and its runs were deleted afterwards (owner decision).
