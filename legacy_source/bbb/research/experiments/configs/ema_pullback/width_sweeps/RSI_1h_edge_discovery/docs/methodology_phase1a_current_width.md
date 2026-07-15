# Methodology — Phase 1A Current Width Sweep

## Isolation

Only one variable is swept:

```text
anchor_stack_width_setup.min_current_width_atr
```

Held constant:

```text
recent_width_atr = 10
width_lookback_bars = 20
untouched lookback = 75
active_bars = 8
entry trigger
risk
exit policy rail per candidate
```

## Why no strict branch first

Strict lower rails were short-biased in Phase 0.

Phase 1A first checks whether the cleaner relaxed lower semantic branch has a stable current-width zone.

Strict can be added later as a control once the semantic width zone is known.

## Why no 2.45 / 2.50

Those are transition comparators.

They are not used in Phase 1A because Phase 1A is about EMA200-compatible lower rails.

## Why no 3.75 / 4.0

Those are wide continuation comparators.

They are a separate hypothesis and should not contaminate the lower semantic width search.
