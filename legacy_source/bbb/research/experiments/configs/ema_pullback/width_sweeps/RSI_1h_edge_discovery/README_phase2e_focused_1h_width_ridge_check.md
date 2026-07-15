# RSI 1h Edge Discovery — Phase 2E Focused 1h Width Ridge Check

## Purpose

Phase 2D found a strong 1h-width candidate:

```text
1h 2.15 w2.25/r2.75/lb35
```

Metrics from Phase 2D:

```text
trades: 163
PnL: +4 679
PF: 1.279
WR: 58.3%
DD: -15.8%
long PF: 1.222
short PF: 1.402
PF gap: 0.180
```

This is promising, but before adding blockers or exit management we need to verify that it is a stable ridge, not a single lucky point.

## Core concern

The key risk is semantic drift:

```text
The stop/TP rail can become too wide relative to anchor-stack width.
```

If the strategy wins because it rides a higher-order trend after a large rail, it is no longer a clean EMA200 bounce strategy.

Therefore Phase 2E keeps:

```text
2.15 as the main rail
2.35 only as an upper comparator
```

and removes `2.45` from the focused search.

## What stays fixed

```text
symbol:
  BTCUSDT

base timeframe:
  5m

EMA stack:
  base close
  fast 100 / anchor 200 / slow 496

trigger:
  touch_anchor

untouched setup:
  lookback 75
  active_bars 8

SL/TP:
  symmetric 1h ATR
  period 14

fees:
  0.04%
```

## What changes

Only 1h-width setup parameters around the discovered ridge:

```text
anchor_stack_width_setup:
  atr_timeframe = 1h
  current_width
  recent_width
  width_lookback_bars
```

## Excluded

```text
RSI blocker
ADX runner
BE / lock
runtime exits
partial TP
trailing
HTF context
asymmetric rails
2.45 transition rail
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase2e_focused_1h_width_ridge_check_fee04.json
```

## Candidate folder

```text
candidates/phase2e_focused_1h_width_ridge_check/
```

## Matrix

Controls:

```text
base 2.15 w11/r12/lb20
base 2.15 w11/r12/lb10
base 2.35 w11/r12/lb20
1h 2.15 w2.25/r2.75/lb35
1h 2.15 w2.25/r2.75/lb50
```

Focused 1h grid:

```text
rail:
  2.15
  2.35

current_width_1h:
  1.90
  2.00
  2.10
  2.20
  2.25
  2.30

recent_width_1h:
  2.65
  2.75
  2.85

lookback:
  lb20
  lb35
  lb50
```

Total:

```text
5 controls + 108 focused candidates = 113 candidates
```

## Main selection rules

Do not select by raw PnL only.

Main candidate should have:

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.12
short PF > 1.12
PF gap target <= 0.20
PF gap hard max <= 0.30
rail = 2.15 preferred
```

## What we are looking for

Good outcome:

```text
A small stable cluster around w2.20/w2.25 and r2.75
with both long and short PF alive,
not only one exact point.
```

Bad outcome:

```text
Only one point works.
Only 2.35 works.
Short side carries everything.
Trade count collapses.
Result looks like trend capture, not EMA200 bounce.
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2e_focused_1h_width_ridge_check_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2e_focused_1h_width_ridge_check_fee04.json
```
