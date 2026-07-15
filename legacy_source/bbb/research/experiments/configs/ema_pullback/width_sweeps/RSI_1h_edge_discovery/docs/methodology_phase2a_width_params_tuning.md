# Methodology — Phase 2A Width Parameters Tuning

## Why this phase exists

Phase 1A proved that current width matters.

Phase 1B showed that transition rail 2.45 remains useful and should not be discarded.

Phase 2A now tunes the width gate internals:

```text
min_recent_width_atr
width_lookback_bars
```

## Isolation

Only these width parameters change:

```text
current_width_atr: w9 or w11
recent_width_atr: r8/r10/r12/r14
width_lookback_bars: lb10/lb20/lb35
```

Held constant:

```text
untouched lookback = 75
active_bars = 8
trigger = touch_anchor
risk = no_risk_filter
no blockers
no contexts
no exit management
```

## Interpretation

Recent width + lookback answers:

```text
Was the stack sufficiently expanded recently,
not only at the current bar?
```

A stricter recent requirement can remove weak pullbacks, but may reduce trade count too much.

A longer lookback can catch prior expansion, but may admit stale trend structures.

A shorter lookback can demand fresh expansion, but may miss valid slow pullbacks.

## Decision principle

Select a region, not a single spike.

Good candidate:

```text
stable across neighboring params
not one-sided
not too sparse
better bad-context behavior
```
