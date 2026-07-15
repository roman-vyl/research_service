# Proposed Phase 2E - Focused 1h Width Ridge Check

## Why

Phase 2D found the best main-rail 1h-width candidate:

```text
1h 2.15 w2/r2.75/lb20
```

It passes the acceptance gate, but needs a focused ridge check before RSI is added.

## Matrix

```text
rail:
  2.15
  2.35

current_width_1h:
  1.90
  2.00
  2.10
  2.20

recent_width_1h:
  2.65
  2.75
  2.85

lookback:
  lb10
  lb20
  lb35
```

Total:

```text
2 * 4 * 3 * 3 = 72 candidates
```

Keep base controls:

```text
base 2.15 w11/r12/lb20
base 2.15 w11/r12/lb10
```

## Acceptance

Carry forward a 1h-width core only if the ridge is stable around neighboring thresholds, not only one point.

Minimum:

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.10
short PF > 1.10
PF gap <= 0.35
```
