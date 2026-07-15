# Phase 0C Findings — 1h ATR Upper Guard Sweep

Batch:

```text
ema200_rsi_1h_edge_phase0c_1h_atr_upper_guard_sweep_fee04
```

Status:

```text
candidates: 15
ok: 15
failed: 0
```

## Executive summary

Phase 0C did not close the upper boundary.

The relaxed branch kept improving all the way to the last tested value:

```text
relaxed_known + 1hATR SL3 / TP3

trades: 339
PnL: +10 727
PF: 1.178
win rate: 56.3%
maxDD: -22.8%
long PF: 1.134
short PF: 1.223
long PnL: +4 127
short PnL: +6 600
```

The strict control also improved at `3.0`:

```text
strict_known + 1hATR SL3 / TP3

trades: 138
PnL: +5 595
PF: 1.310
win rate: 57.2%
maxDD: -14.1%
long PF: 1.198
short PF: 1.473
long PnL: +2 123
short PnL: +3 473
```

## Main conclusion

The original idea of picking a small “neutral ruler” is now questionable.

The best value is again the upper boundary:

```text
Phase 0 coarse:
  best at 2.0 upper boundary

Phase 0B:
  best near 2.45/2.50 upper boundary

Phase 0C:
  best at 3.0 upper boundary
```

This means:

```text
1h ATR symmetric rail is not merely calibrating a local bounce ruler.
It is turning into a wider continuation-style rail.
```

That is not automatically bad, but it changes what Phase 1 means.

If Phase 1 uses `1hATR 3/3`, it is not testing a tiny bounce edge.  
It is testing:

```text
Can width select entries that survive a wide 1h volatility envelope?
```

## Top relaxed candidates

| Mult | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.00 | 339 | 10 727 | 1.178 | 56.3% | -22.8% | 1.134 | 1.223 | 4 127 | 6 600 | 148 | 51 |
| 2.95 | 339 | 8 826 | 1.158 | 56.0% | -22.5% | 1.105 | 1.214 | 3 016 | 5 810 | 149 | 51 |
| 2.90 | 340 | 7 675 | 1.143 | 55.9% | -22.2% | 1.107 | 1.182 | 2 905 | 4 770 | 150 | 51 |
| 2.85 | 341 | 7 454 | 1.146 | 56.0% | -21.9% | 1.151 | 1.142 | 3 860 | 3 594 | 150 | 51 |
| 2.55 | 347 | 6 167 | 1.145 | 56.8% | -24.7% | 1.148 | 1.143 | 3 139 | 3 028 | 150 | 57 |
| 2.70 | 344 | 5 319 | 1.125 | 56.4% | -27.3% | 1.115 | 1.135 | 2 472 | 2 847 | 150 | 53 |
| 2.50 | 347 | 4 745 | 1.119 | 56.2% | -24.3% | 1.137 | 1.101 | 2 730 | 2 014 | 152 | 58 |
| 2.75 | 343 | 4 028 | 1.098 | 56.0% | -27.6% | 1.118 | 1.079 | 2 413 | 1 615 | 151 | 53 |
| 2.65 | 345 | 4 024 | 1.100 | 55.9% | -26.9% | 1.073 | 1.128 | 1 491 | 2 532 | 152 | 53 |
| 2.80 | 342 | 3 755 | 1.091 | 55.8% | -28.0% | 1.091 | 1.092 | 1 877 | 1 879 | 151 | 51 |
| 2.60 | 345 | 3 576 | 1.091 | 55.9% | -26.5% | 1.076 | 1.106 | 1 508 | 2 068 | 152 | 54 |

## Strict control candidates

| Mult | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.00 | 138 | 5 595 | 1.310 | 57.2% | -14.1% | 1.198 | 1.473 | 2 123 | 3 473 | 59 | 27 |
| 2.75 | 138 | 2 060 | 1.137 | 55.1% | -17.1% | 1.051 | 1.261 | 451 | 1 609 | 62 | 28 |
| 2.50 | 138 | 1 574 | 1.119 | 55.1% | -16.1% | 0.989 | 1.318 | -84 | 1 658 | 62 | 30 |
| 2.45 | 139 | 1 186 | 1.092 | 54.7% | -18.9% | 0.984 | 1.248 | -123 | 1 309 | 63 | 31 |

## Relaxed readout

The relaxed branch is strong across the upper range:

```text
2.55:
  PnL +6 167
  PF 1.145
  long PF 1.148
  short PF 1.143

2.85:
  PnL +7 454
  PF 1.146
  long PF 1.151
  short PF 1.142

2.95:
  PnL +8 826
  PF 1.158
  long PF 1.105
  short PF 1.214

3.00:
  PnL +10 727
  PF 1.178
  long PF 1.134
  short PF 1.223
```

The rise is not perfectly smooth, but `3.0` is clearly best by PnL/PF and both sides remain above `1`.

## Strict control readout

Strict also improves materially at `3.0`:

```text
2.45:
  PnL +1 186
  PF 1.092
  long PF 0.984
  short PF 1.248

2.50:
  PnL +1 574
  PF 1.119
  long PF 0.989
  short PF 1.318

2.75:
  PnL +2 060
  PF 1.137
  long PF 1.051
  short PF 1.261

3.00:
  PnL +5 595
  PF 1.310
  long PF 1.198
  short PF 1.473
```

This is important: at `3.0`, strict is no longer only short-side noise. Long side finally becomes positive too.

## Decision

Do not proceed directly to current-width Phase 1 yet.

Reason:

```text
The upper boundary is still not closed.
```

Before large width sweeps, run a final coarse guard:

```text
Phase 0D:
  relaxed_known and strict_known
  1hATR symmetric:
    3.0
    3.25
    3.5
    3.75
    4.0
```

This is intentionally coarse.  
The goal is not precision; the goal is to identify whether `3.0` is a local peak or whether wider rails keep improving.

## If Phase 0D keeps improving

Then there are two possible interpretations:

```text
1. Wide 1h ATR rails are revealing real continuation edge.
2. Symmetric ruler calibration has stopped being a neutral edge test and is turning into a loose hold/continuation proxy.
```

At that point, Phase 1 should be renamed/defined honestly as:

```text
current-width sweep under wide 1h ATR continuation ruler
```

not as local bounce calibration.

## If Phase 0D peaks around 3.0

Then use:

```text
primary:
  1hATR SL3 / TP3

secondary:
  1hATR SL2.85 / TP2.85
  1hATR SL2.55 / TP2.55
```

for Phase 1 current-width sweep.

## Still excluded

Do not add:

```text
RSI blocker
RSI gate
ADX runner
runtime exits
BE / lock
partial TP
trailing
asymmetric rails
```

until the 1h ATR ruler boundary is closed.
