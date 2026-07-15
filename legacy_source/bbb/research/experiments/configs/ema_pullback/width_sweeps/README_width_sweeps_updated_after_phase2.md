# Width sweeps — updated roadmap after Phases 0–2

Copy this folder into repo root so files are located at:

```text
research/experiments/configs/ema_pullback/width_sweeps/
```

## What we already learned

### Phase 0 — baseline vs width sanity

Baseline without width was bad:

```text
no width, SL5/TP14
trades: 1205
PF: ~0.916
win rate: ~26.3%
pnl: ~-6614
max DD: ~-0.757
```

Known width sanity point improved selection:

```text
w7 / r14 / lb35 / SL5 / TP14
trades: 318
PF: ~1.052
win rate: ~31.4%
pnl: ~+1083
max DD: ~-0.175
```

Conclusion: `anchor_stack_width_setup` is useful as an entry-quality filter.

### Phase 1 — current width search

With recent filter almost disabled:

```text
r1 / lb35 / SL5 / TP14
```

The useful zone started much higher than expected:

```text
w9  -> PF ~0.989, pnl ~-227
w10 -> PF ~1.021, pnl ~+311
w12 -> PF ~1.262, pnl ~+1784
```

Conclusion: the main filter is `min_current_width_atr`. Current stack width must be high. Low width thresholds 2–8 do not clean entries enough.

### Phase 2 — SL/TP search on w12/r1/lb35

Main quality baseline selected:

```text
w12 / r1 / lb35 / SL6 / TP14
trades: 143
PF: ~1.262
win rate: ~38.5%
pnl: ~+1991
max DD: ~-0.110
long PF: ~1.232
short PF: ~1.307
high_mfe_low_capture: 3
stop_loss_after_low_mfe: 53
stop_loss_after_bad_context: 88
```

Runner candidate:

```text
w12 / r1 / lb35 / SL5 / TP20
PF: ~1.307
pnl: ~+2398
but lower win rate, higher runner dependence, less clean diagnostic profile
```

Conclusion: use `SL6/TP14` as the clean entry-quality baseline. Keep `SL5/TP20` as a runner branch, not as the main diagnostic config.

## Phase 3 goal

Now we search whether a *recent width expansion requirement* and the `width_lookback_bars` window improve entry quality.

We are not changing trigger, blockers, context, or break-even here.

Fixed baseline for Phase 3:

```text
current width = 12
ATR SL = 6
ATR TP = 14
anchor_stack = 100/200/496
untouched_anchor_setup = lookback 75, active_bars 8
trigger = touch_anchor
no blockers
```

## Files and commands

### Phase 3A — recent width threshold sweep

This tests whether requiring recent stack expansion improves the already good `w12` entry filter.

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase3a_recent_width_sweep_w12_sl6_tp14.json
```

Grid:

```text
current_width = 12
lookback = 35
SL/TP = 6/14

recent_width:
1, 8, 10, 12, 14, 16, 18, 20, 24, 28
```

Interpretation:

```text
r1  = recent filter basically disabled
r12 = recent max must at least match current threshold
r14+ = require prior expansion stronger than current condition
```

### Phase 3B — lookback sweep

This checks whether recent-width memory should be short or long.

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase3b_lookback_sweep_w12_recent_candidates_sl6_tp14.json
```

Grid:

```text
current/recent pairs:
w12/r1
w12/r12
w12/r14
w12/r16
w12/r20

lookback:
20, 35, 50, 75, 100, 150, 200

SL/TP = 6/14
```

Interpretation:

```text
short lookback 20–35:
  recent expansion must be fresh

medium 50–100:
  accepts trend expansion within several hours

long 150–200:
  may include old trend expansion and allow late entries
```

### Phase 3C — optional robustness map

Run only after 3A/3B if needed.

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase3c_width_recent_lookback_robustness_sl6_tp14.json
```

Grid:

```text
current width:
10, 12, 14

selected recent thresholds:
w10: 1, 10, 12, 14, 16
w12: 1, 12, 14, 16, 20
w14: 1, 14, 16, 20, 24

lookback:
35, 75, 100

SL/TP = 6/14
```

Purpose:

```text
Check if w12 is not the only viable current-width zone.
Check if w14 improves quality but overfilters.
Check if w10 can survive when recent width is stricter.
```

## What to compare

Do not choose only by PnL. For entry quality compare:

```text
trades
PF
win_rate
max_drawdown
long_profit_factor
short_profit_factor
high_mfe_high_capture_count
high_mfe_low_capture_count
stop_loss_after_low_mfe
stop_loss_after_bad_context
fees_paid
```

Good sign:

```text
PF >= Phase 2 baseline
both long and short PF > 1
high_mfe_low_capture does not grow
stop_loss_after_low_mfe falls
stop_loss_after_bad_context falls
trade count does not collapse below useful sample size
max_drawdown does not worsen materially
```

Bad sign:

```text
PF improves only because trades collapse to a tiny sample
short side dies again
high_mfe_low_capture grows
drawdown worsens
recent_width requirement blocks good early trend entries
```

## Current preferred baseline before Phase 3

```text
w12 / r1 / lb35 / SL6 / TP14
```

This is the reference config to beat.
