# Methodology — Phase 2C Width ATR Timeframe Sensitivity

## Research question

Phase 2B found a good base ATR-normalized width core.

But we still need to test whether the width measurement itself should be normalized by the same 1h ATR ruler already used by SL/TP.

## Current width definition

Base version:

```text
stack_width / ATR_5m
```

Phase 2C alternative:

```text
stack_width / ATR_1h
```

## Why not use RSI yet

RSI 1h is a separate market-state filter.

Phase 2C stays inside entry-geometry measurement:

```text
volatility normalization of anchor-stack width
```

Adding RSI before this test would mix measurement-scale effects with filter effects.

## Interpretation caution

If 1h ATR width works, it does not mean RSI 1h works.

If 1h ATR width fails, it does not mean RSI 1h fails.

This phase only decides which volatility ruler should normalize anchor-stack width.
