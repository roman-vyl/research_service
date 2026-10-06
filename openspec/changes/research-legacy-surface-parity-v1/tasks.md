## 1. Implementation

- [ ] 1.1 `MaterializeBlock.parity: Literal["strict", "legacy_surface"] = "strict"`.
- [ ] 1.2 Gate: `legacy_surface` rules per Engine field (`realised_trade_count` exact; `return_pct`, `profit_factor`, `win_rate`, `max_drawdown` at 4 decimals; `cumulative_net_r` at 2; `net_pnl` within 0.5); other fields strict; `strict` unchanged. Diagnostics carry the rule applied per failing metric.
- [ ] 1.3 Tests: the 35 smoke cells pass under `legacy_surface` and 29 fail under `strict`; one unit off at the stored precision fails; `net_pnl` 0.5 passes and 0.51 fails; default block is `strict`.
- [ ] 1.4 `make verify` and `openspec validate --all --strict` (1.7.0).

## 2. Verification on the Mac (on command)

- [ ] 2.1 Set `materialize.parity: "legacy_surface"` on `btcusdt_p.ema500.calc_smoke_width_band` and Calculate its 5 rows again; report how many pass.
