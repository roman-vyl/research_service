# RSI 1h Edge Discovery — Phase 1A Final README

## Status

Phase 1A completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase1a_current_width_semantic_rulers_fee04
candidates: 30
ok: 30
failed: 0
duration_sec: 980.3
```

## What Phase 1A tested

Phase 0 selected lower semantic 1h ATR rails:

```text
A1: 1hATR SL1.90 / TP1.90
A2: 1hATR SL2.15 / TP2.15
A3: 1hATR SL2.35 / TP2.35
```

Phase 1A kept those rails fixed and tested **current anchor-stack width**:

```text
anchor_stack_width_setup.min_current_width_atr
```

Swept values:

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

Held constant:

```text
recent_width_atr = 10
width_lookback_bars = 20
untouched_anchor_setup.lookback = 75
untouched_anchor_setup.active_bars = 8
```

No RSI, ADX, runtime exits, BE, trailing, HTF context, asymmetric exits, or transition rails were included.

## Main result

Phase 1A confirms that **current width is a real edge-shaping parameter**.

The result splits into zones:

```text
w6–w7:
  too loose/noisy
  many trades
  high fees
  weak PF
  many bad-context stops

w8:
  borderline
  turns positive, but short side remains weak

w9–w11:
  main semantic working zone
  enough trades
  works across several rails
  side balance can stay alive

w12–w14:
  fewer trades
  often short-carried
  long side frequently weak

w16:
  high-selectivity zone
  very high PF
  both sides positive in this run
  but only 49 trades per rail
```

## Carry-forward candidates

These are the candidates to keep as the main semantic branch:

| Rail | Width | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.90 | w9 | 356 | 2 817 | 1.089 | 56.7% | -15.3% | 1.109 | 1.068 | 1 745 | 1 072 | 154 | 70 |
| 1.90 | w11 | 204 | 3 030 | 1.181 | 57.8% | -25.8% | 1.130 | 1.240 | 1 175 | 1 855 | 86 | 49 |
| 2.15 | w10 | 283 | 4 255 | 1.164 | 56.5% | -23.4% | 1.032 | 1.335 | 467 | 3 788 | 123 | 53 |
| 2.15 | w11 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 | 1 514 | 2 054 | 88 | 48 |
| 2.35 | w9 | 350 | 3 878 | 1.102 | 55.7% | -21.9% | 1.105 | 1.098 | 2 025 | 1 853 | 155 | 61 |
| 2.35 | w11 | 203 | 3 934 | 1.187 | 56.7% | -25.0% | 1.160 | 1.217 | 1 784 | 2 150 | 88 | 45 |

## Best-by-rail reference

| Rail | Width | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.90 | w10 | 284 | 2 889 | 1.123 | 56.7% | -25.5% | 0.980 | 1.311 | -262 | 3 151 | 123 | 57 |
| 1.90 | w11 | 204 | 3 030 | 1.181 | 57.8% | -25.8% | 1.130 | 1.240 | 1 175 | 1 855 | 86 | 49 |
| 1.90 | w16 | 49 | 1 117 | 1.349 | 63.3% | -10.6% | 1.430 | 1.286 | 596 | 520 | 18 | 12 |
| 2.15 | w11 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 | 1 514 | 2 054 | 88 | 48 |
| 2.15 | w14 | 80 | 1 715 | 1.279 | 58.8% | -11.4% | 0.929 | 1.847 | -271 | 1 986 | 33 | 17 |
| 2.15 | w16 | 49 | 2 877 | 1.906 | 65.3% | -9.1% | 1.437 | 2.436 | 737 | 2 140 | 17 | 11 |
| 2.35 | w11 | 203 | 3 934 | 1.187 | 56.7% | -25.0% | 1.160 | 1.217 | 1 784 | 2 150 | 88 | 45 |
| 2.35 | w14 | 80 | 1 862 | 1.271 | 57.5% | -13.4% | 0.934 | 1.804 | -276 | 2 138 | 34 | 17 |
| 2.35 | w16 | 49 | 3 226 | 1.913 | 65.3% | -9.1% | 1.447 | 2.439 | 837 | 2 389 | 17 | 10 |

## Interpretive decisions

### Main semantic baseline

If we need one main candidate:

```text
2.15 + w11
```

Reason:

```text
trades: 204
PF: 1.190
PnL: +3 568
long PF: 1.151
short PF: 1.234
not too sparse
not too wide
not transition-contaminated
```

### Broad balanced baseline

```text
2.35 + w9
```

Reason:

```text
trades: 350
PF: 1.102
long PF: 1.105
short PF: 1.098
best side balance with enough trades
```

### High-selectivity branch

```text
w16
```

Reason:

```text
very high PF
low drawdown
both sides positive
```

But:

```text
only 49 trades per rail
must not be treated as proven baseline without robustness checks
```

## Visual files

Charts copied into this package:

```text
charts/phase1a/01_win_rate_by_width.png
charts/phase1a/02_total_pf_by_width.png
charts/phase1a/03_long_pf_by_width.png
charts/phase1a/04_short_pf_by_width.png
charts/phase1a/05_max_dd_by_width.png
charts/phase1a/06_total_pnl_by_width.png
charts/phase1a/07_long_pnl_by_width.png
charts/phase1a/08_short_pnl_by_width.png
charts/phase1a/phase1a_width_metrics.csv
```

## Phase 1A conclusion

```text
The current-width edge exists.
The main practical zone is w9–w11.
w16 is promising but belongs to a separate high-selectivity robustness branch.
```

---

# What comes next

Phase 1B should not be a huge blind sweep.

With Phase 1A information, Phase 1B should test transition rails:

```text
2.45 / 2.45
2.50 / 2.50
```

on selected widths:

```text
w8:
  borderline guard

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

This gives:

```text
2 rails × 6 widths = 12 candidates
```

Purpose:

```text
Check whether 2.45–2.50 still behave like semantic EMA200 rails,
or whether they already start transition/wide-continuation behavior.
```
