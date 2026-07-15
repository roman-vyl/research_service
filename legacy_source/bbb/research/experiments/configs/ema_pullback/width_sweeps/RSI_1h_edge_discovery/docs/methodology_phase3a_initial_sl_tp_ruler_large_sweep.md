# Methodology — Phase 3A Initial SL/TP Ruler Large Sweep

## Why this phase exists

The previous 1h-width tests used symmetric 1h SL/TP rails such as 2.15/2.15.

That is not comparable to the old base-timeframe initial search, where good candidates used much larger TP/SL ratios:

```text
SL6/TP14 = 2.33R
SL4/TP10 = 2.50R
SL5/TP20 = 4.00R
```

Therefore this phase searches hourly TP values with comparable RR ratios.

## What is not tested

No blockers.
No ADX runner.
No BE/lock.
No runtime exit management.
No RSI exits.
No asymmetric long/short exits.

This is still initial fixed SL/TP only.

## Interpretation

A 1h TP candidate is not main if it only wins because:

```text
short side carries everything
trade count collapses
RR is too small compared with old initial logic
result appears to be trend-capture rather than EMA200 bounce
```
