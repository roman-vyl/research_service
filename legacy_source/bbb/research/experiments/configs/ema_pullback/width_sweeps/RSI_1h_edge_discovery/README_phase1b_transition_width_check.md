# RSI 1h Edge Discovery — Phase 1B Transition Width Check

## Purpose

Phase 1A found the working semantic current-width area:

```text
w9–w11
```

It also found a high-selectivity branch:

```text
w16
```

Phase 1B checks whether transition rails still behave like EMA200-compatible rails, or whether they start drifting toward the wider continuation behavior.

## Rails

```text
2.45 / 2.45
2.50 / 2.50
```

These are not lower semantic rails. They are transition comparators.

## Widths

Selected from Phase 1A:

```text
w8:
  borderline lower guard

w9:
  broad balanced baseline

w10:
  PnL / short-heavy check

w11:
  main quality compromise

w14:
  upper selective guard

w16:
  high-selectivity branch
```

Total:

```text
2 rails × 6 widths = 12 candidates
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase1b_transition_width_check_fee04.json
```

## Candidate folder

```text
candidates/phase1b_transition_width_check/
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase1b_transition_width_check_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase1b_transition_width_check_fee04.json
```

## What to compare against Phase 1A

Compare each width against its Phase 1A semantic neighbors:

```text
w9:
  compare 2.45/2.50 vs 1.90/2.15/2.35

w10:
  compare 2.45/2.50 vs 2.15/2.35

w11:
  compare 2.45/2.50 vs 1.90/2.15/2.35

w16:
  check if high-selectivity edge survives transition rails
```

## Decision rules

### Transition rail remains useful if

```text
PF improves without side collapse
long and short remain above or near 1
drawdown does not expand too much
trade count remains interpretable
bad-context stops do not rise sharply
```

### Transition rail is suspicious if

```text
PnL rises but long/short balance collapses
result becomes short-carried
maxDD expands materially
only w16 works with very few trades
2.50 behaves much more like wide continuation than semantic entry edge
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
```
