# EMA 200 naked-edge experiments — final README for Phases 0–5

This document closes the first block of naked EMA 200 edge experiments.

Scope:

```text
symbol: BTCUSDT
base timeframe: 5m
anchor_stack: EMA 100 / EMA 200 / EMA 496, source close, base timeframe
anchor: EMA 200
direction: ema_anchor_stack_trend
trigger: touch_anchor
main setups:
  untouched_anchor_setup
  anchor_stack_width_setup
blockers: no_blockers
risk: no_risk_filter
trade_sides: long + short
fees: 0.0003
slippage: 0.0001
```

The goal was not to build the final strategy. The goal was to answer whether there is any bare edge around EMA 200 pullbacks before adding HTF context, signal exits, trailing, break-even, ADX/DI, RSI blockers, or complex trade management.

---

## Executive verdict

There is a real edge, but it is not a generic EMA 200 touch edge.

The useful edge appears only when the EMA stack has enough width/expansion. In plain trading terms:

```text
Do not buy/sell every EMA 200 touch.
Trade pullbacks to EMA 200 only when the EMA stack is already expanded enough.
```

The experiments separated two regimes:

```text
A. Strict continuation regime
   w12/r14/wlb20 + SL6/TP14
   fewer trades, cleaner edge, lower drawdown, strong short side

B. Relaxed medium/bounce regime
   w9/r10/wlb20 + SL4/TP10
   more trades, lower PF, dirtier shorts, higher drawdown
```

These are not one strategy with one optimum. They are two different regimes.

---

# Phase 0 — sanity: no width vs first width filter

## Result

Baseline without width was bad:

```text
no width / SL5 / TP14
trades: ~1205
PF: ~0.916
win rate: ~26.3%
pnl: ~-6614
max DD: ~-0.757
```

Known first width point improved the system:

```text
w7 / r14 / lb35 / SL5 / TP14
trades: ~318
PF: ~1.052
win rate: ~31.4%
pnl: ~+1083
max DD: ~-0.175
```

## Interpretation

EMA 200 touch by itself is not an edge. Width is the first real filter.

---

# Phase 1 — current width search

Phase 1 isolated `min_current_width_atr` with recent width almost disabled:

```text
recent = 1
width_lookback_bars = 35
SL/TP = 5/14
```

Useful area appeared only high enough:

```text
w9  -> PF ~0.989, pnl ~-227
w10 -> PF ~1.021, pnl ~+311
w12 -> PF ~1.262, pnl ~+1784
```

## Interpretation

The main entry-quality parameter is current stack width.

```text
min_current_width_atr must be high.
Low width thresholds do not clean entries enough.
```

Early conclusion:

```text
w12 is the first serious current-width baseline.
```

---

# Phase 2 — SL/TP search on w12/r1/lb35

Phase 2 searched ATR SL/TP around the first serious width point:

```text
w12 / r1 / lb35
```

Best clean baseline:

```text
w12 / r1 / lb35 / SL6 / TP14

trades: ~143
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
but lower win rate and more runner dependence
```

## Interpretation

A wide stop/take profile was better than local small exits at this stage.

This started suggesting:

```text
The setup is not just a small EMA 200 bounce.
It may be a continuation after pullback.
```

---

# Phase 3A/3B — recent width and width lookback

Phase 3 tested whether recent width expansion improves the already useful current width filter.

Fixed:

```text
current width = 12
SL/TP = 6/14
```

## Key result: recent <= current is redundant

`r1` and `r12` gave the same result across lookbacks:

```text
w12 / r1 or r12 / any tested lookback / SL6 / TP14
trades: ~143
PF: ~1.262
pnl: ~+1991
```

Reason:

```text
if current width >= 12,
then the inclusive recent window already contains current width >= 12.
So recent <= 12 adds no filter.
```

Do not optimize these again unless current width is lowered:

```text
r1 / r8 / r10 / r12
```

## Best strict continuation baseline

```text
w12 / r14 / width_lb20 / untouched75 / active8 / SL6 / TP14

trades: ~138
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

## Lookback interpretation

For `r14`, fresh expansion was better:

```text
w12/r14/lb20  -> PF ~1.410, pnl ~+2993
w12/r14/lb35  -> PF ~1.402, pnl ~+2942
w12/r14/lb50  -> PF ~1.356, pnl ~+2566
w12/r14/lb75+ -> PF ~1.335, pnl ~+2435
```

## Interpretation

For strict continuation, the market should be recently expanded. Old expansion lets weaker/late entries through.

---

# Phase 4A — small exits on strict setup

Phase 4A tested small SL/TP on the best strict entry:

```text
w12 / r14 / width_lb20
untouched75 / active8
```

Strict reference stayed best:

```text
w12/r14/wlb20/SL6/TP14

trades: ~138
PF: ~1.409
win rate: ~40.6%
pnl: ~+2993
max DD: ~-0.110
long PF: ~1.270
short PF: ~1.647
```

Best smaller/medium candidate on strict setup:

```text
w12/r14/wlb20/SL5/TP12

trades: ~140
PF: ~1.196
pnl: ~+1214
long PF: ~1.168
short PF: ~1.238
```

## Interpretation

Small exits do not beat continuation exits on strict width setup.

```text
Strict width setup is not local EMA 200 bounce.
It is trend continuation after strong EMA-stack expansion.
```

Rejected as main branch on strict setup:

```text
SL 2.5–4 with TP 4–10
```

---

# Phase 4B — relaxed width with smaller exits

Phase 4B lowered width strictness and tested smaller exits.

Best useful relaxed candidate:

```text
w9 / r10 / width_lb20 / SL4 / TP10

trades: ~357
PF: ~1.168
win rate: ~34.7%
pnl: ~+3195
max DD: ~-0.182
long PF: ~1.300
short PF: ~1.024
```

## Interpretation

Relaxing width creates a second regime:

```text
more trades
lower PF
higher drawdown
dirtier short side
```

This is not better than strict continuation on quality, but it gives much more sample and positive gross behavior.

Bad relaxed area:

```text
w8/r10
```

It produces many trades, but shorts break and drawdown worsens.

---

# Phase 5A — refine exits around w9/r10

Phase 5A fixed:

```text
w9 / r10 / width_lb20
untouched75 / active8
```

and refined SL/TP around `SL4/TP10`.

Best candidate remained:

```text
w9/r10/wlb20/SL4/TP10

trades: ~357
PF: ~1.168
win rate: ~34.7%
pnl: ~+3195
max DD: ~-0.182
long PF: ~1.300
short PF: ~1.024
high_mfe_high_capture: 41
high_mfe_low_capture: 11
stop_loss_after_low_mfe: 143
stop_loss_after_bad_context: 233
```

Close but worse:

```text
w9/r10/wlb20/SL4/TP12

trades: ~354
PF: ~1.163
pnl: ~+3177
long PF: ~1.280
short PF: ~1.033
high_mfe_low_capture: 17
stop_loss_after_bad_context: 244
```

## Interpretation

`SL4/TP10` is the local optimum for relaxed/medium mode.

`TP12` is not clearly better. It keeps similar PnL but increases low-capture and bad-context signs.

Working stop for relaxed mode:

```text
SL ~4 ATR
```

Smaller stop gets hit too often. Wider stop makes errors more expensive and worsens drawdown.

---

# Phase 5B — entry neighborhood with medium exits

Phase 5B tested neighboring width filters with medium exits.

All 63 candidates completed successfully.

## Best overall is still strict continuation

```text
trades 138, PF 1.410, win 40.6%, pnl +2993, DD -0.110, long PF 1.270, short PF 1.647
high MFE: 27 / 138 = 19.6%
high_mfe_low_capture: 2
bad_context stops: 82
```

This remains the cleanest candidate by PF, drawdown, short quality, and bad-context control.

## Best relaxed candidate remains w9/r10/SL4/TP10

```text
trades 357, PF 1.168, win 34.7%, pnl +3195, DD -0.182, long PF 1.300, short PF 1.024
high MFE: 52 / 357 = 14.6%
high_mfe_low_capture: 11
bad_context stops: 233
```

It gives more trades and slightly higher net PnL than strict baseline, but much worse quality:

```text
strict: 138 trades, PF 1.410, DD -0.110, bad_context 82
relaxed: 357 trades, PF 1.168, DD -0.182, bad_context 233
```

## w9/r12 is interesting but short side dies

Best w9/r12 variants:

```text
w9/r12/wlb20/SL4/TP10:
trades 305, PF 1.154, win 35.4%, pnl +2295, DD -0.153, long PF 1.302, short PF 0.959
bad_context stops: 197

w9/r12/wlb20/SL4/TP11:
trades 303, PF 1.162, win 33.3%, pnl +2487, DD -0.184, long PF 1.352, short PF 0.919
bad_context stops: 202
```

This improves drawdown / bad-context vs w9/r10 and keeps decent PF, but short PF falls below 1.

Interpretation:

```text
r12 cleans some bad entries,
but it does not solve short side.
```

## w8/r10 is too dirty

```text
trades 425, PF 1.064, win 33.2%, pnl +1403, DD -0.256, long PF 1.130, short PF 0.988
bad_context stops: 284
```

Interpretation:

```text
w8 is too loose for both-side trading.
Do not continue w8 unless testing long-only experiments.
```

## w10/r12 is too weak

```text
trades 256, PF 1.059, win 34.8%, pnl +661, DD -0.167, long PF 1.090, short PF 1.014
bad_context stops: 167
```

It is more balanced than many relaxed variants, but the edge is too small.

## Phase 5B conclusion

The neighborhood search did not find a better relaxed both-side setup than:

```text
w9/r10/wlb20/SL4/TP10
```

It also confirmed that strict continuation remains the highest-quality bare edge:

```text
w12/r14/wlb20/SL6/TP14
```

---

# MFE / runner implication

The batch summaries do not include full trade-by-trade MFE/MAE distributions, but the quality counters show enough to justify the next research direction.

Definitions:

```text
MFE = Maximum Favorable Excursion
MAE = Maximum Adverse Excursion
```

For long:

```text
MFE = max(high after entry before exit) - entry
MAE = entry - min(low after entry before exit)
```

For short:

```text
MFE = entry - min(low after entry before exit)
MAE = max(high after entry before exit) - entry
```

High-MFE counts:

```text
strict w12/r14/SL6/TP14:
  high MFE trades: 27 / 138 = 19.6%
  high_mfe_low_capture: 2

relaxed w9/r10/SL4/TP10:
  high MFE trades: 52 / 357 = 14.6%
  high_mfe_low_capture: 11
```

Interpretation:

```text
There is a tail of trades with high potential continuation.
But simply increasing fixed TP for all trades did not solve it.
```

So the next exit idea should not be:

```text
raise TP globally
```

It should be:

```text
fixed normal exit for ordinary trades
conditional runner/trailing only for high-quality context, probably HTF-aligned
```

---

# Final baselines after naked EMA 200 edge experiments

## Strict continuation baseline

```text
w12 / r14 / width_lb20 / untouched75 / active8 / SL6 / TP14
```

Use this as the clean baseline for future context/runner experiments.

Pros:

```text
highest PF
lowest drawdown
best short quality
lowest bad-context count
strongest proof that width expansion is real edge
```

Cons:

```text
only ~138 trades
may miss many smaller bounce opportunities
large rails, not local EMA 200 bounce
```

## Relaxed medium/bounce baseline

```text
w9 / r10 / width_lb20 / untouched75 / active8 / SL4 / TP10
```

Use this as the exploratory high-sample branch.

Pros:

```text
~357 trades
positive both-side result
good long side
more suitable for testing filters/context
```

Cons:

```text
PF much lower
drawdown much higher
short barely profitable
bad-context stops much higher
```

## Long-bias observation

Across relaxed experiments, long side carries most of the edge. Short side is fragile.

This means future both-side work should not assume symmetry just because component logic is side-aware.

---

# What we learned

## Confirmed

```text
1. Naked EMA 200 touch is not enough.
2. EMA-stack width is the first real edge filter.
3. Current width matters more than generic recent width.
4. recent <= current is redundant because the current bar is inside the recent window.
5. Fresh expansion matters for strict continuation.
6. Strict setup wants wide continuation exits, not small bounce exits.
7. Relaxed setup has a separate medium/bounce branch, but it is dirty.
8. Shorts are the main weak point in relaxed mode.
9. A high-MFE tail exists, but global larger TP is not the right solution.
```

## Rejected or deprioritized

```text
generic no-width EMA 200 touch
w8 both-side relaxed mode
small exits on strict setup
global TP increase for all trades
r1/r8/r10/r12 recent thresholds when current width is already 12
blind SL/TP sweeping without context
```

---

# Recommended next stage

This closes the naked-edge phase.

Next phase should add context/trade-management, not more blind EMA 200 parameter grinding.

Priority order:

```text
1. Run side-split diagnostics if not already done:
   long-only / short-only for strict and relaxed baselines.

2. Add HTF context to classify trades:
   aligned / countertrend / neutral.

3. Test conditional runner:
   normal exit for non-HTF-aligned trades;
   runner/trailing/EMA-cross exit only for HTF-aligned trades.

4. Use full trade reports, not batch summaries, to inspect:
   MFE
   MAE
   capture ratio
   giveback
   bars_to_mfe
   bars_from_mfe_to_exit
   HTF regime at entry

5. Only after that decide:
   one unified strategy
   or two branches:
     strict continuation
     relaxed medium/bounce
```

Do not add break-even or complex trailing before understanding side/context split.
