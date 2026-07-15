# RSI 1h Edge Discovery — Phase 2A Width Parameters Tuning

## Purpose

Phase 2A follows Phase 1A and Phase 1B.

Phase 1A established that current width matters and that the main working zone is:

```text
w9–w11
```

Phase 1B showed that transition rail `2.45 / 2.45` is not garbage and can be a clean side-balanced comparator, especially at `w11`.

Phase 2A now tunes the **other width parameters**:

```text
recent_width_atr
width_lookback_bars
```

while keeping the search focused around the proven current-width zone.

## Main question

```text
Which recent-width and lookback parameters stabilize the w9/w11 entry edge
across semantic and transition-quality 1h ATR rails?
```

## What is swept

### Current width

```text
w9:
  broad balanced baseline

w11:
  quality compromise baseline
```

### Recent width

```text
r8:
  looser recent expansion requirement

r10:
  Phase 1A/1B baseline

r12:
  stricter recent expansion requirement

r14:
  strict recent expansion control
```

### Width lookback

```text
lb10:
  short recent expansion memory

lb20:
  Phase 1A/1B baseline

lb35:
  longer expansion memory
```

### Rails

```text
2.15 / 2.15:
  semantic primary

2.35 / 2.35:
  semantic upper

2.45 / 2.45:
  transition-quality comparator
```

Total:

```text
2 current widths × 4 recent widths × 3 lookbacks × 3 rails = 72 candidates
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase2a_width_params_tuning_fee04.json
```

## Candidate folder

```text
candidates/phase2a_width_params_semantic_transition/
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2a_width_params_tuning_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2a_width_params_tuning_fee04.json
```

## Why Phase 2A does not include 1.90

`1.90` was useful as a conservative semantic ruler, but Phase 1A/1B showed stronger candidates around:

```text
2.15
2.35
2.45
```

Phase 2A should not over-expand the matrix. `1.90` can be reintroduced later if we need a lower-risk conservative control.

## Why Phase 2A does not include 2.50

`2.50` is a boundary transition rail. It performed fine in Phase 1B, but `2.45` is cleaner for this tuning step:

```text
2.45 + w11:
  balanced long/short PF

2.50:
  still useful but slightly closer to transition/wide-continuation contamination
```

Keep `2.50` for a later confirmation batch if `2.45` survives Phase 2A.

## Why Phase 2A does not include w16

`w16` is promising but only had 49 trades per rail in Phase 1A/1B.

It belongs to a separate high-selectivity robustness branch, not to the main width-parameter tuning.

## What to compare

Do not select by PnL alone.

Compare:

```text
PF
PnL
maxDD
win rate
long PF
short PF
long PnL
short PnL
trade count
fees paid
stop_loss_after_bad_context
stop_loss_after_low_mfe
high_mfe_high_capture_count
high_mfe_low_capture_count
```

## Good outcome

A good Phase 2A result is not necessarily the highest PnL.

Preferred result:

```text
works on both w9 and w11,
or clearly explains why one is better;
survives at least two rails;
long and short remain above or near 1;
bad-context stops decrease;
drawdown does not expand materially;
trade count remains interpretable.
```

## Bad outcome

Reject candidates that:

```text
work only on one rail spike;
become short-only;
collapse long PF below 1;
produce high PnL with huge DD;
collapse to too few trades;
only work on 2.45 but fail 2.15/2.35.
```

## Still excluded

```text
RSI blocker
RSI gate
ADX runner
runtime exits
BE / lock
partial TP
trailing
HTF context
asymmetric rails
wide continuation rails 3.75/4.00
high-selectivity-only w16 branch
```

Reason:

```text
We are still isolating the entry edge created by anchor-stack width.
```
