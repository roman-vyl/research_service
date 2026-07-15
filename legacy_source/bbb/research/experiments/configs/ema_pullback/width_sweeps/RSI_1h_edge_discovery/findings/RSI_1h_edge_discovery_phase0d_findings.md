# Phase 0D Findings — 1h ATR Wide Guard Sweep

Batch:

```text
ema200_rsi_1h_edge_phase0d_1h_atr_wide_guard_sweep_fee04
```

Status:

```text
candidates: 10
ok: 10
failed: 0
duration_sec: 335.1
```

## Executive summary

Phase 0D confirms that this research branch is no longer calibrating a small neutral bounce ruler.

The best values are wide 1h ATR rails:

```text
best relaxed:
  relaxed_known + 1hATR SL3.75 / TP3.75

best strict:
  strict_known + 1hATR SL4 / TP4
```

This means the current edge is behaving like a **wide continuation / swing envelope**, not a local pullback bounce exit.

## Best relaxed candidate

```text
relaxed_known + 1hATR SL3.75 / TP3.75

trades: 307
PnL: +15 639
PF: 1.236
win rate: 57.0%
maxDD: -32.5%
long PF: 1.064
short PF: 1.435
long PnL: +2 273
short PnL: +13 366
```

Important:

```text
This is high PnL, but it is strongly short-carried.
Long side is only barely positive.
Drawdown is materially worse than the 2.5–3.0 zone.
```

## Best strict candidate

```text
strict_known + 1hATR SL4 / TP4

trades: 131
PnL: +9 540
PF: 1.404
win rate: 61.8%
maxDD: -22.1%
long PF: 1.302
short PF: 1.556
long PnL: +4 276
short PnL: +5 264
```

This is the cleanest quality point in Phase 0D.

Strict at `4.0` has fewer trades, but both sides are clearly positive and PF is much stronger.

## Full relaxed sweep

| Mult | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.00 | 339 | 10 727 | 1.178 | 56.3% | -22.8% | 1.134 | 1.223 | 4 127 | 6 600 | 148 | 51 |
| 3.25 | 325 | 13 090 | 1.196 | 56.9% | -25.2% | 1.107 | 1.291 | 3 678 | 9 411 | 140 | 42 |
| 3.50 | 313 | 8 381 | 1.144 | 55.6% | -30.2% | 1.031 | 1.267 | 947 | 7 433 | 139 | 38 |
| 3.75 | 307 | 15 639 | 1.236 | 57.0% | -32.5% | 1.064 | 1.435 | 2 273 | 13 366 | 132 | 34 |
| 4.00 | 305 | 15 013 | 1.240 | 57.4% | -30.4% | 1.048 | 1.473 | 1 663 | 13 350 | 130 | 30 |

## Full strict sweep

| Mult | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.00 | 138 | 5 595 | 1.310 | 57.2% | -14.1% | 1.198 | 1.473 | 2 123 | 3 473 | 59 | 27 |
| 3.25 | 135 | 5 831 | 1.307 | 57.8% | -14.6% | 1.227 | 1.422 | 2 535 | 3 296 | 57 | 24 |
| 3.50 | 134 | 5 499 | 1.273 | 57.5% | -20.1% | 1.167 | 1.426 | 1 999 | 3 500 | 57 | 23 |
| 3.75 | 131 | 8 511 | 1.377 | 60.3% | -21.1% | 1.258 | 1.555 | 3 489 | 5 022 | 52 | 20 |
| 4.00 | 131 | 9 540 | 1.404 | 61.8% | -22.1% | 1.302 | 1.556 | 4 276 | 5 264 | 50 | 17 |

## Interpretation

### Relaxed branch

Relaxed peaks at `3.75`, but the quality is not as clean as the PnL suggests:

```text
3.75:
  PnL +15 639
  PF 1.236
  maxDD -32.5%
  long PF 1.064
  short PF 1.435
```

At `4.0`, PnL remains high but does not improve:

```text
4.0:
  PnL +15 013
  PF 1.240
  maxDD -30.4%
  long PF 1.048
  short PF 1.473
```

So relaxed has a wide continuation plateau around `3.75–4.0`, but the edge is increasingly short-heavy.

### Strict branch

Strict keeps improving into `4.0`:

```text
3.00:
  PnL +5 595
  PF 1.310

3.25:
  PnL +5 831
  PF 1.307

3.50:
  PnL +5 499
  PF 1.273

3.75:
  PnL +8 511
  PF 1.377

4.00:
  PnL +9 540
  PF 1.404
```

This means strict is now the cleaner quality branch for wide 1h ATR rails.

## Decision

Do not run Phase 1 as “ruler calibration” anymore.

The correct framing is now:

```text
Phase 1 should be current-width sweep under wide 1h ATR continuation rails.
```

Recommended Phase 1 should include two rails:

```text
quality rail:
  strict/relaxed comparison under 1hATR 4.0/4.0

sensitivity rail:
  1hATR 3.0/3.0 or 3.25/3.25
```

Why include a smaller sensitivity rail:

```text
4.0 has better PF/quality, but it may be too wide and more continuation-like.
3.0–3.25 helps detect whether width edge exists before very wide holding dominates.
```

## Recommended Phase 1 design

Phase 1 should sweep current width while holding:

```text
distance:
  timeframe = 1h
  period = 14
  symmetric SL/TP = 4.0 primary
```

Profiles should be split instead of pretending one profile is universal:

```text
relaxed-style branch:
  recent = 10
  lookback = 20
  current width sweep

strict-style branch:
  recent = 14
  lookback = 20
  current width sweep
```

Current width values:

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

Optional include `no_width` as negative control for both branches.

## Still do not add

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

The next question is now:

```text
Under wide 1h ATR continuation rails,
which current width zone actually creates the entry edge?
```
