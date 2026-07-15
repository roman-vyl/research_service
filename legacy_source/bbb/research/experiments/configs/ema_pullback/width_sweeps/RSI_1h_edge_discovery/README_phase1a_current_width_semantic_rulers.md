# RSI 1h Edge Discovery — Phase 1A Current Width Sweep

## Purpose

Phase 1A starts after Phase 0 separated lower semantic EMA200 rulers from transition/wide-continuation rails.

The goal is to answer one question:

```text
Under lower 1h ATR rails that still make sense for EMA200 pullback,
which current-width zone of the anchor stack creates the entry edge?
```

This phase is **not** testing RSI, ADX, runtime exits, BE, trailing, or continuation holding.

---

# Inputs from Phase 0

Phase 0 selected three lower semantic rails:

```text
A1 — conservative semantic:
  1hATR SL1.90 / TP1.90

A2 — primary semantic:
  1hATR SL2.15 / TP2.15

A3 — upper semantic:
  1hATR SL2.35 / TP2.35
```

These are used because:

```text
1.90:
  lower-risk / lower-DD semantic ruler

2.15:
  best balance of PF, PnL, DD, side balance

2.35:
  upper semantic comparator before transition zone
```

Excluded from Phase 1A:

```text
2.45 / 2.50:
  transition comparators, Phase 1B later

3.75 / 4.00:
  wide continuation comparators, Phase 1C later
```

---

# Batch

```text
batches/ema200_rsi_1h_edge_phase1a_current_width_semantic_rulers_fee04.json
```

# Candidate folder

```text
candidates/phase1a_current_width_semantic_rulers/
```

---

# Matrix

## Branch

Only relaxed-style branch first:

```text
recent_width_atr = 10
width_lookback_bars = 20
untouched_anchor_setup.lookback = 75
untouched_anchor_setup.active_bars = 8
```

Reason:

```text
Phase 0 lower semantic zone was cleanest on relaxed_known.
Strict lower rails were short-biased and are not the primary branch.
```

## Rails

```text
1hATR 1.90 / 1.90
1hATR 2.15 / 2.15
1hATR 2.35 / 2.35
```

## Current width sweep

```text
w6
w7
w8
w9
w10
w11
w12
w13
w14
w16
```

Total:

```text
3 rails × 10 current widths = 30 candidates
```

---

# Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase1a_current_width_semantic_rulers_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase1a_current_width_semantic_rulers_fee04.json
```

---

# What to compare

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

Preferred width zone:

```text
PF improves across multiple rails
both long and short stay alive
drawdown does not explode
trade count does not collapse too much
bad-context stops decrease
result is not a one-point spike
```

Reject:

```text
one-side-only result
large PnL with weak side balance
higher width that only works on 2.35 but fails on 1.90/2.15
trade count too small to trust
DD expansion that suggests the rail/width is too loose
```

---

# Expected interpretation

## If one width zone wins across 1.90 / 2.15 / 2.35

Then we have a real current-width edge candidate.

Example:

```text
w10–w12 stable across all rails
```

Next step:

```text
Phase 2:
  recent width / width lookback tuning around that current-width zone
```

## If only 2.35 works and 1.90/2.15 fail

Then the edge may depend on upper/transition behavior.

Next step:

```text
Phase 1B:
  add 2.45 / 2.50 transition comparators
```

## If all lower semantic rails fail after width sweep

Then the earlier profits likely came from wider holding / transition behavior, not clean EMA200 pullback edge.

Next step:

```text
reconsider entry setup or move to separate continuation branch
```

---

# Still excluded

Do not add yet:

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

Reason:

```text
First isolate whether current anchor-stack width creates entry edge
under EMA200-compatible rails.
```
