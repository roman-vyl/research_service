# RSI 1h Edge Discovery — Phase 3A Initial SL/TP Ruler Large Sweep

## Purpose

This phase compares old base-timeframe initial SL/TP rulers against new base/1h ATR SL/TP rulers on the preserved best entry cores.

Important correction:

```text
Hourly SL 2.15 / TP 3.0 is only 1.40R.
That is too small compared with old working initial ratios.
```

Old working initial ratios:

```text
strict:
  SL6 / TP14 = 2.33R

relaxed:
  SL4 / TP10 = 2.50R

runner comparator:
  SL5 / TP20 = 4.00R
```

So this package searches 1h ATR TP values around proper 2.33R / 2.5R / 3R / 4R ratios.

## What is fixed

```text
symbol: BTCUSDT
base timeframe: 5m
EMA stack: base close, fast 100 / anchor 200 / slow 496
trigger: touch_anchor
untouched setup: lookback 75, active_bars 8
fees: 0.04%
```

Excluded:

```text
RSI blocker
ADX runner
BE / lock
runtime exits
partial TP
trailing
HTF context
asymmetric long/short rails
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase3a_initial_sl_tp_ruler_large_sweep_fee04.json
```

## Candidate folder

```text
candidates/phase3a_initial_sl_tp_ruler_large_sweep/
```

## Total candidates

```text
1322
```

## Preserved entry cores

```text
1. old strict refined:
   base width w12/r14/lb20

2. old strict original:
   base width w12/r1/lb35

3. old relaxed refined:
   base width w9/r10/lb20

4. current base sharp:
   base width w11/r12/lb10

5. current base stability:
   base width w11/r12/lb20

6. Phase 2E 1h symmetric:
   1h width w1.9/r2.75/lb35

7. Phase 2E 1h performance/symmetry:
   1h width w2.2/r2.75/lb35

8. Phase 2E 1h performance-only:
   1h width w2.0/r2.75/lb20

9. Phase 2D original:
   1h width w2.25/r2.75/lb35
```

## Locked old litmus candidates

These are included unchanged.

```text
old strict refined:
  base w12/r14/lb20 + base SL6/TP14

old strict runner:
  base w12/r14/lb20 + base SL5/TP20

old strict original:
  base w12/r1/lb35 + base SL6/TP14
  base w12/r1/lb35 + base SL5/TP20

old relaxed:
  base w9/r10/lb20 + base SL4/TP10
  base w9/r10/lb20 + base SL4/TP12
```

Also included as modern controls:

```text
base w11/r12/lb10 + 1h SL2.15/TP2.15
base w11/r12/lb20 + 1h SL2.15/TP2.15
1h w1.9/r2.75/lb35 + 1h SL2.15/TP2.15
1h w2.2/r2.75/lb35 + 1h SL2.15/TP2.15
1h w2.0/r2.75/lb20 + 1h SL2.15/TP2.15
```

## Sweep structure

### A. Base ATR SL/TP ratio sweep

```text
SL base ATR:
  4, 5, 6, 7

RR:
  2.00, 2.25, 2.33, 2.50, 2.75, 3.00, 3.50, 4.00
```

### B. Base ATR exact TP sweep

Exact base TP anchors are included to preserve old integer-style comparisons:

```text
SL4:
  TP8, TP9, TP10, TP11, TP12, TP14, TP16

SL5:
  TP10, TP12, TP14, TP16, TP18, TP20

SL6:
  TP12, TP14, TP15, TP16, TP18, TP20, TP24

SL7:
  TP14, TP16, TP18, TP20, TP24, TP28
```

### C. 1h ATR SL/TP ratio sweep

```text
SL 1h ATR:
  1.75, 2.00, 2.15, 2.35, 2.50

RR:
  2.00, 2.25, 2.33, 2.50, 2.75, 3.00, 3.50, 4.00
```

This means examples like:

```text
SL2.15 / TP5.00 ≈ 2.33R
SL2.15 / TP5.38 ≈ 2.50R
SL2.15 / TP6.45 ≈ 3.00R
SL2.15 / TP8.60 ≈ 4.00R
```

### D. 1h ATR TP anchor sweep

```text
TP 1h ATR:
  4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 10.0
```

Filtered to roughly valid 2R-4.75R depending on SL.

### E. Cross-ruler comparators

Smaller diagnostic cross-ruler section:

```text
base SL / 1h TP
1h SL / base TP
```

This is included to test whether stop ruler and TP ruler should be separated.

## Selection rule

Do not choose winner by PnL alone.

Main candidate should preserve:

```text
trades >= 100
PF >= 1.18
long PF > 1.10
short PF > 1.10
PF gap target <= 0.20
PF gap hard max <= 0.30
RR ratio not too small
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase3a_initial_sl_tp_ruler_large_sweep_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase3a_initial_sl_tp_ruler_large_sweep_fee04.json
```
