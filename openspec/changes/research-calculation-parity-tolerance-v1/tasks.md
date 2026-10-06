## 1. Implementation

- [x] 1.1 Gate: integers exact; other metrics `|a − e| ≤ max(ABS_TOL[field], 1e-3 × max(|a|, |e|))` with the fixed field table; `_parity` gets the result bindings.
- [x] 1.2 Tests: the 35 smoke cells pass; a 0.2 % change fails; floors near zero for `return_pct`, `net_pnl`, `cumulative_net_r`; side path `long.net_pnl` uses the `net_pnl` floor; trade count off by one fails.
- [x] 1.3 `make verify` and `openspec validate --all --strict` (1.7.0).

## 2. Verification on the Mac (on command)

- [ ] 2.1 Deploy, then Calculate the 5 rows of `btcusdt_p.ema500.calc_smoke_width_band` again; report how many pass.
