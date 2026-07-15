# Methodology — Lower 1h ATR Ruler

## Problem with 3–4x 1h ATR

On a 5m chart, 3–4x 1h ATR can be larger than the local EMA-stack structure.

That means a trade may no longer be a clean EMA200 pullback trade. It may become a wide continuation hold.

## Phase 0E target

Find a lower rail that still measures the EMA200 pullback area.

## Do not use only PnL

High PnL at large multipliers can come from rare large continuation moves.

Phase 0E should prioritize:

```text
side balance
PF
drawdown
stable trade count
reduced bad-context stops
semantic proximity to EMA200 pullback
```
