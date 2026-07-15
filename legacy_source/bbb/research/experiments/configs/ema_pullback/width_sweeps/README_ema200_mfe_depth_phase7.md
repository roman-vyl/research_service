# EMA200 MFE Depth Diagnostic Batches — Phase 7

## Purpose

These configs are not intended as final production strategy candidates.

They are measurement batches for the new v6 report diagnostics.

The goal is to estimate the depth and timing of favorable excursions inside real executed trades:

```text
entry -> actual exit
```

The report only measures MFE/MAE inside the actual lifetime of a trade. Therefore, for diagnostic runs we use larger take-profit values so trades stay open longer and the report can observe deeper MFE before the actual exit.

No post-exit lookahead.
No shadow trades.
No hypothetical continuation.
No runner logic.

## Main question

We want to learn:

```text
How often do EMA200 pullback trades produce a large favorable excursion?
How high are the p75/p90 MFE values?
How much MAE is required to survive those moves?
How many bars does it take to reach MFE?
Does a wider TP merely increase hold time, or does it expose a real high-MFE tail?
```

## Base branches

### Relaxed medium / bounce branch

```text
w9 / r10 / width_lb20 / untouched75 / active8 / SL4 / TP10
```

This branch has more trades and is useful for statistics.

### Strict continuation branch

```text
w12 / r14 / width_lb20 / untouched75 / active8 / SL6 / TP14
```

This branch is cleaner and useful as a quality control sample.

## Files

### Phase 7A — TP extension sweep

Batch spec:

```text
research/experiments/configs/ema_pullback/width_sweeps/width_phase7a_ema200_mfe_depth_tp_sweep.json
```

Candidates:

```text
Relaxed:
  w9/r10/wlb20/SL4/TP10
  w9/r10/wlb20/SL4/TP14
  w9/r10/wlb20/SL4/TP20
  w9/r10/wlb20/SL4/TP30
  w9/r10/wlb20/SL4/TP40

Strict:
  w12/r14/wlb20/SL6/TP14
  w12/r14/wlb20/SL6/TP20
  w12/r14/wlb20/SL6/TP24
  w12/r14/wlb20/SL6/TP30
  w12/r14/wlb20/SL6/TP40
```

Run first.

This is the main diagnostic batch.

### Phase 7B — SL breathing-room sweep

Batch spec:

```text
research/experiments/configs/ema_pullback/width_sweeps/width_phase7b_ema200_mfe_depth_sl_breathing_sweep.json
```

Candidates:

```text
Relaxed:
  TP30 with SL4/SL5/SL6
  TP40 with SL4/SL5/SL6

Strict:
  TP30 with SL6/SL8/SL10
  TP40 with SL6/SL8/SL10
```

Run only after Phase 7A shows a meaningful high-MFE tail.

This checks whether wider stops are actually required to observe the tail, or whether they only increase MAE/drawdown.

### Combined batch

```text
research/experiments/configs/ema_pullback/width_sweeps/width_phase7_ema200_mfe_depth_combined.json
```

Contains all Phase 7A + 7B candidates.

Use only if runtime is not a concern.

## Commands

From repo root:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase7a_ema200_mfe_depth_tp_sweep.json
```

Optional follow-up:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase7b_ema200_mfe_depth_sl_breathing_sweep.json
```

Combined:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase7_ema200_mfe_depth_combined.json
```

## What to inspect

Prefer the compact summary artifacts:

```text
research/results/runs/<RUN_ID>.summary.json
```

Look at:

```text
metrics.path_diagnostics_summary.total
metrics.path_diagnostics_summary.by_side
metrics.path_diagnostics_summary.by_exit_reason
```

Especially:

```text
trade_count
avg_mfe_pct
median_mfe_pct
p75_mfe_pct
p90_mfe_pct

avg_mae_pct
median_mae_pct
p75_mae_pct
p90_mae_pct

avg_capture_ratio
median_capture_ratio

avg_giveback_pct
median_giveback_pct

avg_bars_to_mfe
median_bars_to_mfe
avg_bars_to_mae
median_bars_to_mae

reference_levels_available_count
first_take_profit_count
first_stop_loss_count
ambiguous_first_level_count
no_reference_level_hit_count
```

## How to interpret Phase 7A

If TP increases and:

```text
p90_mfe_pct grows,
median/avg bars_to_mfe remains reasonable,
MAE does not explode,
trade_count remains usable,
```

then the entry branch has a measurable high-MFE tail.

If TP increases and:

```text
p90_mfe_pct barely improves,
MAE increases,
bars_to_mfe becomes very large,
PF/drawdown degrade badly,
```

then wider TP is mostly just keeping trades open longer without revealing useful continuation.

## How to interpret Phase 7B

If wider SL increases MFE but MAE increases proportionally or more, then the tail is expensive and may not be tradable.

If wider SL increases p75/p90 MFE while MAE stays controlled, then the original stop may be too tight for runner-style exits.

## Important limitation

This is executed-window diagnostics only.

A trade that exits early cannot tell us what happened after exit.

These batches intentionally use wider TP values to keep trades alive longer, but they still do not simulate post-exit continuation.

A separate event-study layer would be needed later for fixed forward-window analysis after TP/exit events.
