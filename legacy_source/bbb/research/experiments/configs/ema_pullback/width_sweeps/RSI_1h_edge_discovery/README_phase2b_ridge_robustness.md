# RSI 1h Edge Discovery — Phase 2B Ridge Robustness

## Purpose

Phase 2A found the first real quality ridge:

```text
w11 / r12 / lb10
```

Meaning:

```text
current_width >= 11 base ATR
recent_max_width >= 12 base ATR
within the last 10 base 5m candles
```

Phase 2B checks whether this is:

```text
a stable parameter region
```

or:

```text
a single-point overfit spike
```

## What is swept

### Current width

```text
w10:
  lower neighbor around ridge

w11:
  Phase 2A ridge center

w12:
  upper neighbor around ridge
```

### Recent width

```text
r11:
  lower recent-width neighbor

r12:
  Phase 2A ridge center

r13:
  upper recent-width neighbor
```

### Width lookback

```text
lb5:
  fresh expansion only = 25 minutes on 5m candles

lb10:
  Phase 2A ridge center = 50 minutes on 5m candles

lb15:
  slightly slower expansion memory = 75 minutes on 5m candles
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
3 current widths × 3 recent widths × 3 lookbacks × 3 rails = 81 candidates
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase2b_ridge_robustness_fee04.json
```

## Candidate folder

```text
candidates/phase2b_ridge_robustness_w11_r12_lb10/
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2b_ridge_robustness_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2b_ridge_robustness_fee04.json
```

## Interpretation rules

### Ridge confirmed if

```text
neighboring values around w11/r12/lb10 remain profitable;
PF does not collapse outside the exact center;
both long and short remain alive;
drawdown does not explode;
at least two rails show similar parameter preference;
lb10 or nearby lb5/lb15 remains consistently better than stale long memory.
```

### Ridge suspicious if

```text
only exact w11/r12/lb10 works;
neighboring w10/w12 or r11/r13 collapse;
only one rail works;
result becomes one-sided;
trade count becomes too small;
PnL improves only with worse drawdown or short-only behavior.
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
wide continuation rails
high-selectivity w16 branch
```

Reason:

```text
This phase must confirm entry-core robustness before adding filters/exits.
```
