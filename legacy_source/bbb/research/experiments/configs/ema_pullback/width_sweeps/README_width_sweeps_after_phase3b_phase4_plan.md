# EMA pullback width sweeps — Phase 3B summary and Phase 4 plan

Copy this folder into repo root so files are located at:

```text
research/experiments/configs/ema_pullback/width_sweeps/
```

## Phase 3B summary

Common setup:

```text
BTCUSDT 5m
anchor_stack: EMA 100 / 200 / 496 close, base timeframe
direction: ema_anchor_stack_trend
trigger: touch_anchor
setups: untouched_anchor_setup AND anchor_stack_width_setup
blockers: no_blockers
risk: no_risk_filter
trade_sides: long + short
```

Phase 3B tested `width_lookback_bars` for selected `min_recent_width_atr` thresholds while keeping:

```text
current width = 12
SL/TP = 6/14
```

### Key findings

`recent <= current` is redundant:

```text
w12 / r1 or r12 / any tested width lookback / SL6 / TP14
trades: 143
PF: ~1.262
win rate: ~38.5%
pnl: ~+1991
```

Reason: if current width is already `>= 12`, the inclusive recent window already contains the current bar. So `recent <= 12` adds no filter.

Do not spend more time on these recent thresholds unless current width is lowered:

```text
r1 / r8 / r10 / r12
```

Best balanced result from Phase 3B:

```text
w12 / r14 / width_lb20 / SL6 / TP14

trades: 138
PF: ~1.410
win rate: ~40.6%
pnl: ~+2993
max DD: ~-0.110
long PF: ~1.270
short PF: ~1.647
high_mfe_low_capture: 2
stop_loss_after_low_mfe: 52
stop_loss_after_bad_context: 82
```

`r14` prefers fresh expansion:

```text
w12/r14/lb20  -> PF ~1.410, pnl ~+2993, trades 138
w12/r14/lb35  -> PF ~1.402, pnl ~+2942, trades 139
w12/r14/lb50  -> PF ~1.356, pnl ~+2566, trades 139
w12/r14/lb75+ -> PF ~1.335, pnl ~+2435, trades 140
```

Interpretation:

```text
For moderate recent threshold r14, useful signal is fresh width expansion.
Old expansion starts to admit weaker or later entries.
```

Strict branch candidates:

```text
w12/r20/lb20:
  trades: 76
  PF: ~1.474
  win rate: ~42.1%
  pnl: ~+1657
  long PF: ~1.438
  short PF: ~1.528

w12/r20/lb100:
  trades: 103
  PF: ~1.411
  win rate: ~41.7%
  pnl: ~+2168
  long PF: ~1.190
  short PF: ~1.823
```

Current main baseline:

```text
w12 / r14 / width_lb20 / untouched_lb75 / active_bars8 / SL6 / TP14
```

## Why Phase 4

Current best profile uses large rails for an EMA 200 pullback:

```text
SL = 6 ATR
TP = 14 ATR
```

That may be catching trend continuation after a strong pullback, not a local EMA 200 bounce.

Phase 4 checks another hypothesis:

```text
If setup conditions are relaxed and stop/take rails are smaller,
we may get more trades with smaller profit targets and still acceptable entry quality.
```

This is not pure PnL optimization. The goal is to identify the nature of the setup:

```text
local EMA 200 bounce:
  should survive on SL ~2.5–4 and TP ~4–10

trend continuation after width expansion:
  will continue to prefer SL ~5–6 and TP ~14–20
```

## Phase 4 files and commands

### Phase 4A — smaller exits on best Phase 3B entry filter

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase4a_small_exit_area_w12_r14_lb20.json
```

Fixed entry setup:

```text
width: w12/r14/width_lb20
untouched: lookback75 / active_bars8
```

Exit pairs:

```text
2.5/4, 2.5/5, 2.5/6, 2.5/8
3/5, 3/6, 3/8, 3/10
3.5/6, 3.5/8, 3.5/10
4/6, 4/8, 4/10, 4/12
4.5/8, 4.5/10, 4.5/12
5/8, 5/10, 5/12
6/14 reference
```

Purpose:

```text
Check whether the current best entry filter works with local bounce exits.
```

### Phase 4B — relaxed width + smaller exits

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase4b_relaxed_width_small_exits.json
```

Entry filters:

```text
w8/r10/width_lb20
w9/r10/width_lb20
w10/r10/width_lb20
w10/r12/width_lb20
w10/r12/width_lb35
w12/r14/width_lb20 reference
```

Untouched setup remains:

```text
lookback75 / active_bars8
```

Exit pairs:

```text
2.5/5
3/6
3/8
3.5/7
4/8
4/10
5/10
6/14 reference
```

Purpose:

```text
Lower width strictness to get more trades, then see whether smaller SL/TP keeps quality acceptable.
```

### Phase 4C — relaxed untouched setup + smaller exits

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase4c_relaxed_untouched_and_small_exits.json
```

Entry filters:

```text
w10/r12/width_lb20
w12/r14/width_lb20
```

Untouched variants:

```text
lookback40 / active_bars6
lookback50 / active_bars6
lookback60 / active_bars8
lookback75 / active_bars8 reference
```

Exit pairs:

```text
3/6
3.5/7
4/8
4/10
5/10
6/14 reference
```

Purpose:

```text
Test whether untouched_anchor_setup was too strict for bounce-style exits.
```

## How to judge Phase 4

Do not select by PnL alone.

Compare:

```text
total_trades
profit_factor
win_rate
max_drawdown
long_profit_factor
short_profit_factor
long_trades
short_trades
high_mfe_high_capture_count
high_mfe_low_capture_count
stop_loss_after_low_mfe
stop_loss_after_bad_context
fees_paid
```

Good smaller-exit candidate:

```text
more trades than baseline
PF remains > 1.15 ideally
both long and short PF > 1
drawdown improves or stays close
stop_loss_after_low_mfe does not explode
high_mfe_low_capture decreases or stays low
```

Bad candidate:

```text
trade count rises but PF collapses
one side dies, especially shorts
fees eat most gross PnL
win rate rises only because TP is tiny
stop_loss_after_bad_context rises sharply
```

## Interpretation rules

If small exits work only after relaxing setup:

```text
EMA 200 bounce has a separate regime.
Need separate bounce-style branch.
```

If small exits fail but SL6/TP14 remains best:

```text
This setup is not a local bounce.
It is a trend-continuation setup after strong width expansion.
```

If relaxed width works with smaller exits:

```text
Current width filter was overfitted to runner exits.
A looser entry filter plus smaller TP may be more stable.
```

If strict width remains best:

```text
Width expansion is the core edge.
Next steps should focus on context filters / runner exits, not local bounce exits.
```
