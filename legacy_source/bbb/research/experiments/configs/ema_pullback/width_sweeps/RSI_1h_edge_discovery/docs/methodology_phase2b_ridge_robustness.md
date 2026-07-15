# Methodology — Phase 2B Ridge Robustness

## Why Phase 2B exists

Phase 2A found a strong candidate:

```text
w11/r12/lb10
```

But one good point is not enough.

Phase 2B tests the surrounding neighborhood to check whether the result is robust.

## Search region

The search is intentionally local:

```text
current_width:
  10, 11, 12

recent_width:
  11, 12, 13

lookback:
  5, 10, 15
```

This is not a new broad sweep. It is ridge confirmation.

## Why no RSI yet

RSI is postponed because adding it now would hide whether the entry edge itself is stable.

Only after the ridge is confirmed should RSI 1h be added as a blocker/context layer.

## Why no w16 here

w16 is a high-selectivity branch with few trades. It is promising but different from the main entry-core hypothesis.

It should be tested separately in Phase 2C.
