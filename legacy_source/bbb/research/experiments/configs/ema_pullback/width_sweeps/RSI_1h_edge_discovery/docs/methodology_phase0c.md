# Methodology — RSI 1h Edge Discovery

## Why Phase 0C exists

Phase 0B found the best relaxed candidate at 2.45, with 2.50 close behind.

That means the optimum may still be above the previous grid boundary.

Phase 0C is a boundary guard before spending a larger Phase 1 budget.

## Isolation rule

Phase 0C changes only the symmetric 1h ATR multiplier.

It does not change:

```text
width setup
untouched setup
entry trigger
RSI filters
runner management
stop management
take management
```

## After Phase 0C

Only after Phase 0C should Phase 1 current-width sweep be generated.
