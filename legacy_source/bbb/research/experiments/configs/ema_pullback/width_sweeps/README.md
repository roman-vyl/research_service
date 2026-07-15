# Anchor Stack Width batch configs

Copy this `research/experiments/configs/ema_pullback/width_sweeps/` directory into repo root.

Run order:

1. `width_phase0_baseline_known_good.json` — sanity compare no width vs known 7/14/35.
2. `width_phase1_current_width_sweep.json` — isolate `min_current_width_atr`.
3. `width_phase2_recent_width_sweep.json` — sweep `min_recent_width_atr` around current widths 6/7/8. Prune if Phase 1 points elsewhere.
4. `width_phase3_lookback_sweep.json` — sweep `width_lookback_bars` around provisional pairs.
5. `width_phase4_exit_policy_sweep.json` — test top width configs with several ATR SL/TP policies.
6. `width_phase5_break_even_overlay_optional.json` — optional only after finalists; adds `break_even_stop` under `exit_management`.

Important metrics to compare:
- trades, PF, win_rate, net pnl, max_drawdown
- long/short PF and win_rate
- TP/SL counts
- `stop_loss_after_low_mfe`, `high_mfe_low_capture`, `high_mfe_high_capture`
- width setup counters: `current_width_too_narrow`, `recent_width_never_expanded`, `allowed_count`

Baseline assumptions:
- BTCUSDT 5m
- anchor_stack 100/200/496 close/base
- untouched_anchor_setup lookback 75, active_bars 8
- trigger touch_anchor
- no blockers
- fees 0.0003, slippage 0.0001
- Phase 1-4: no break-even, only ATR SL/TP in exit_policy
