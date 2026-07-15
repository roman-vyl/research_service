# EMA pullback width sweeps — Phase 4A/4B summary and Phase 5 package

Copy this folder into repo root so files are located at:

```text
research/experiments/configs/ema_pullback/width_sweeps/
```

## Phase 4A summary — small exits on strict best setup

Fixed entry setup:

```text
w12 / r14 / width_lb20
untouched_anchor_setup: lookback75 / active_bars8
```

Phase 4A tested smaller ATR stop/take rails against the strict Phase 3B baseline.

Main result:

```text
Strict reference:
w12/r14/wlb20/SL6/TP14

trades: 138
PF: ~1.409
win rate: ~40.6%
pnl: ~+2993
max DD: ~-0.110
long PF: ~1.270
short PF: ~1.647
```

Best smaller/medium candidate on the same strict setup:

```text
w12/r14/wlb20/SL5/TP12

trades: 140
PF: ~1.196
win rate: ~37.9%
pnl: ~+1214
long PF: ~1.168
short PF: ~1.238
```

Conclusion:

```text
On strict width setup, small SL/TP does not beat continuation exits.
The strict setup is not a local EMA 200 bounce setup.
It behaves like trend continuation after strong EMA-stack expansion.
```

Rejected as main branch on strict setup:

```text
SL 2.5–4 with TP 4–10
```

They were mostly negative or weak. The edge improved as TP widened, which supports continuation interpretation.

## Phase 4B summary — relaxed width + small/medium exits

Phase 4B relaxed width filters and tested smaller exits.

Best useful relaxed candidate:

```text
w9 / r10 / width_lb20 / SL4 / TP10

trades: 357
PF: ~1.168
win rate: ~34.7%
pnl: ~+3195
max DD: ~-0.182
long PF: ~1.300
short PF: ~1.024
```

Why it matters:

```text
+ much more trades than strict baseline
+ both long and short remain slightly profitable
+ smaller rails are closer to bounce/medium logic
```

Why it is dangerous:

```text
- drawdown is much worse than strict baseline
- bad-context count is much higher
- short side is only barely profitable
- fees are much larger because trade count is higher
```

Weak/dirty area:

```text
w8/r10
```

It gives many trades but short side mostly breaks. Example best-ish case:

```text
w8/r10/wlb20/SL4/TP10
trades: ~425
PF: ~1.064
long PF: ~1.130
short PF: ~0.988
max DD: ~-0.256
```

Balanced but weak area:

```text
w10/r12/wlb20/SL4/TP10
trades: ~256
PF: ~1.059
long PF: ~1.090
short PF: ~1.014
```

Conclusion:

```text
We now have two separate branches:

A. Strict continuation:
   w12/r14/wlb20/SL6/TP14
   fewer trades, higher PF, lower DD, better short quality

B. Relaxed bounce/medium:
   w9/r10/wlb20/SL4/TP10
   more trades, lower PF, higher DD, dirtier short side
```

Do not merge these into one “best” setup. They are different regimes.

## Phase 5 goals

Phase 5 should not repeat huge blind sweeps. It should answer three focused questions:

```text
1. Is w9/r10/SL4/TP10 locally optimal, or is nearby SL/TP better?
2. Is w9/r10 truly the best relaxed width zone, or do w9/r12 / w10/r10 / w10/r12 improve balance?
3. Are shorts the main reason relaxed mode is dirty, and do they need separate context/exit treatment?
```

No break-even here.
No HTF context here.
No trigger/setup semantic changes here.

## Phase 5 files and commands

### Phase 5A — refine SL/TP around relaxed candidate w9/r10

Command:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase5a_relaxed_bounce_exit_refine_w9_r10.json
```

Fixed entry:

```text
w9 / r10 / width_lb20
untouched lookback75 / active_bars8
```

Exit grid:

```text
3.5/8, 3.5/9, 3.5/10, 3.5/11
4/8,   4/9,   4/10,   4/11,   4/12
4.5/9, 4.5/10,4.5/11,4.5/12
5/10,  5/11,  5/12,   5/14
6/14 reference
```

Interpretation:

```text
If 4/10 remains best:
  relaxed mode is a medium continuation/bounce hybrid.

If 4.5/11 or 5/12 improves:
  the setup still wants more continuation than local bounce.

If 3.5/8 or 4/8 improves:
  local bounce branch is real, but Phase 4B grid was too coarse.
```

### Phase 5B — entry neighborhood with medium exits

Command:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase5b_entry_neighborhood_medium_exits.json
```

Entry filters:

```text
w8/r10/wlb20
w9/r10/wlb20
w9/r12/wlb20
w10/r10/wlb20
w10/r12/wlb20
w10/r12/wlb35
w12/r14/wlb20 reference
```

Exits:

```text
4/9
4/10
4/11
4.5/10
4.5/11
4.5/12
5/10
5/12
6/14 reference
```

Interpretation:

```text
If w9/r12 improves short PF without killing trade count:
  relaxed mode needs slightly stricter recent width.

If w10/r10 improves balance:
  current width matters more than recent.

If w8 stays dirty:
  do not relax below w9 for both-sides trading.
```

### Phase 5C — side split diagnostics

Command:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase5c_side_split_diagnostics.json
```

This runs selected configs as:

```text
long only
short only
long + short
```

Configs:

```text
relaxed_main:
  w9/r10/wlb20/SL4/TP10

relaxed_short_bias:
  w9/r10/wlb20/SL4.5/TP10

relaxed_wider:
  w9/r10/wlb20/SL5/TP12

balanced_mid:
  w10/r12/wlb20/SL4/TP10

strict_reference:
  w12/r14/wlb20/SL6/TP14
```

Purpose:

```text
Check if relaxed mode should be long-only for now,
or whether short side can survive with slightly different exits/filters.
```

## What to compare in Phase 5

Do not rank by PnL only.

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

Good relaxed candidate:

```text
trades >= 250
PF >= 1.15
short PF >= 1.0, ideally >= 1.05
long PF remains > 1.15
max DD not worse than ~-0.20
bad-context does not explode further
fees do not consume most gross PnL
```

Bad relaxed candidate:

```text
profit comes only from longs
short PF < 1
drawdown > strict baseline by too much
high_mfe_low_capture grows
more trades but no quality improvement
```

## Current working baselines

Strict continuation baseline:

```text
w12/r14/wlb20/SL6/TP14
```

Relaxed/medium baseline:

```text
w9/r10/wlb20/SL4/TP10
```

These are separate branches. Future architecture may need separate profiles or context policies for them.
