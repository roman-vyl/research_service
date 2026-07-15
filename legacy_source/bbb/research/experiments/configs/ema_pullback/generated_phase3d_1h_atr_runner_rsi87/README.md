# Phase 3E — selected Phase 3D candidates + break-even at runner

Purpose: retest the best Phase 3D pilot candidates with one additional managed stop rule:
when the ADX/DI runner phase starts, move the active stop to break-even.

Common strategy shape:
- symbol BTCUSDT, base timeframe 5m, fee 0.04%, slippage 0.01%
- EMA stack: fast=100, anchor=200, slow=496, close/base
- setups: `anchor_stack_width_setup` base ATR `w9/r10/lb20` + `untouched_anchor_setup` lookback 75, active_bars 8
- trigger: `touch_anchor`
- blockers: `no_blockers`
- initial exits: ATR(1h, 14) stop and take
- runner activation: ADX40 + DI alignment on base/5m
- when runner starts: initial TP disabled
- runtime exit in runner: RSI(5m, 14) 87/13
- NEW in this package: `break_even_stop` activated at `phase_at_least: runner`, no buffer

Selected candidates:

| Candidate | Initial SL | Initial TP | RR | Why included |
|---|---:|---:|---:|---|
| `phase3e_1h_runner_rsi87_be_w9_r10_lb20_sl1h_1p2_tp1h_4p8_rr4_fee04` | 1.2 × ATR(1h) | 4.8 × ATR(1h) | 4.0 | lower-stop comparator; previously PnL ~20.4k, PF ~1.167, gap ~0.081 |
| `phase3e_1h_runner_rsi87_be_w9_r10_lb20_sl1h_1p4_tp1h_5p6_rr4_fee04` | 1.4 × ATR(1h) | 5.6 × ATR(1h) | 4.0 | best mid-stop pilot; previously PnL ~28.4k, PF ~1.224, gap ~0.023 |
| `phase3e_1h_runner_rsi87_be_w9_r10_lb20_sl1h_1p6_tp1h_6p4_rr4_fee04` | 1.6 × ATR(1h) | 6.4 × ATR(1h) | 4.0 | mid/high stop; previously PnL ~26.9k, PF ~1.200, gap ~0.053 |
| `phase3e_1h_runner_rsi87_be_w9_r10_lb20_sl1h_1p8_tp1h_7p2_rr4_fee04` | 1.8 × ATR(1h) | 7.2 × ATR(1h) | 4.0 | strong pilot; previously PnL ~38.8k, PF ~1.283, gap ~0.085 |
| `phase3e_1h_runner_rsi87_be_w9_r10_lb20_sl1h_2_tp1h_8_rr4_fee04` | 2.0 × ATR(1h) | 8.0 × ATR(1h) | 4.0 | best pilot by PF/PnL/symmetry; previously PnL ~41.1k, PF ~1.286, gap ~0.024 |


Run from repo root after copying this package over the repository:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/generated_phase3e_1h_atr_runner_rsi87_be/phase3e_1h_atr_runner_rsi87_be_selected_w9_r10_lb20_ulb75_ab8_fee04.batch.json
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/generated_phase3e_1h_atr_runner_rsi87_be/phase3e_1h_atr_runner_rsi87_be_selected_w9_r10_lb20_ulb75_ab8_fee04.batch.json
```

Manual single-candidate run configs are also in `candidates/`.


Note: `*.batch.json` is for `research.experiments.cli run-batch`. Individual open strategy configs are in `candidates/`. The `*.inline_strategy_collection.json` is included only as a convenience collection, not as the batch spec.
