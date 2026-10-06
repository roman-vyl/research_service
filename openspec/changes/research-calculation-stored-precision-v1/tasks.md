## 1. Implementation

- [ ] 1.1 `Metric.decimals: int | None` (0..12); reject it on `integer` metrics.
- [ ] 1.2 Parity: with `decimals = d`, pass when `|actual − expected| ≤ 0.5 × 10^−d + 1e-9`; otherwise the current rule; diagnostics name the rule per failing metric.
- [ ] 1.3 Tests: rounding-only differences pass with `decimals`, a difference of one stored unit fails, no `decimals` keeps the old result, `decimals` on `integer` rejected.
- [ ] 1.4 `make verify` and `openspec validate --all --strict` (1.7.0).

## 2. Verification on the Mac (on command)

- [ ] 2.1 Add `decimals` to the metrics of `btcusdt_p.ema500.calc_smoke_width_band` (fractions and profit factor 4, cumulative R 2, net PnL 0) and Calculate its 5 rows again; report how many pass.
