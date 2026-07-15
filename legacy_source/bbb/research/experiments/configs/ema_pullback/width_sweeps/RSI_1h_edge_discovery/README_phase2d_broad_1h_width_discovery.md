# RSI 1h Edge Discovery — Phase 2D Broad 1h Width Discovery

## Purpose

Phase 2D is a broad but bounded search for a 1h ATR width candidate that keeps EMA200 bounce semantics.

This is not strict coordinate mapping. It is pragmatic candidate discovery:

```text
anchor_stack_width_setup.atr_timeframe = "1h"
```

## Fixed strategy contract

```text
symbol: BTCUSDT
base timeframe: 5m
EMA stack: base close, fast 100 / anchor 200 / slow 496
trigger: touch_anchor
untouched setup: lookback 75, active_bars 8
SL/TP: symmetric 1h ATR, period 14
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
asymmetric rails
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase2d_broad_1h_width_discovery_fee04.json
```

## Candidate folder

```text
candidates/phase2d_broad_1h_width_discovery/
```

## Matrix

Base controls:

```text
7 candidates
```

Main 1h-width grid:

```text
current_width_1h:
  1.75, 2.00, 2.25, 2.50, 2.75, 3.00, 3.25

recent_delta:
  +0.25, +0.50, +0.75

lookback:
  lb10, lb20, lb35, lb50

rails:
  2.15, 2.35
```

Total main grid:

```text
168 candidates
```

Transition tail:

```text
rail:
  2.45

current_width_1h:
  2.25, 2.50, 2.75

recent_delta:
  +0.25, +0.50

lookback:
  lb20, lb35
```

Total transition tail:

```text
12 candidates
```

Total batch:

```text
187 candidates
```

## Rail interpretation

```text
2.15:
  main EMA200 bounce rail

2.35:
  upper semantic comparator

2.45:
  transition / possible higher-order trend capture
```

If only 2.45 works, do not call it a replacement for the EMA200 bounce core.

## Main candidate acceptance

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.10
short PF > 1.10
PF gap <= 0.35
```

Store separately:

```text
balanced leader
profit leader
short-heavy leader
low-DD leader
high-sample leader
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2d_broad_1h_width_discovery_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2d_broad_1h_width_discovery_fee04.json
```
