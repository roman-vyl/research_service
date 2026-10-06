## 1. Implementation

- [ ] 1.1 Gate constants `REL_TOL = 1e-3`, `ABS_TOL = 1e-6`; integers exact; rule otherwise unchanged.
- [ ] 1.2 Tests: the 35 smoke cells pass; a 0.2 % difference fails; trade count off by one fails; a value at zero vs 1e-7 passes.
- [ ] 1.3 `make verify` and `openspec validate --all --strict` (1.7.0).

## 2. Verification on the Mac (on command)

- [ ] 2.1 Deploy, then Calculate the 5 rows of `btcusdt_p.ema500.calc_smoke_width_band` again; report how many pass.
