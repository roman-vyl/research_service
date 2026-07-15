# Current state — EMA200 runner exit research

## Scope

This document summarizes the current EMA200 exit-management research state before fee-mode reruns.

Do not treat this as final strategy selection. Current results are research signals.

## Existing EMA200 entry branches

### Strict continuation branch

```text
anchor_stack: EMA 100 / 200 / 496, close, base timeframe
width setup: w12 / r14 / width_lb20
untouched setup: lookback75 / active_bars8
trigger: touch_anchor
blockers: no_blockers
risk: no_risk_filter
trade sides: long + short
initial exits: SL6 ATR / TP14 ATR
```

Interpretation:

```text
Cleaner continuation branch.
Fewer trades.
Better PF.
Historically both-side; not simply long-only.
```

### Relaxed medium branch

```text
anchor_stack: EMA 100 / 200 / 496, close, base timeframe
width setup: w9 / r10 / width_lb20
untouched setup: lookback75 / active_bars8
trigger: touch_anchor
blockers: no_blockers
risk: no_risk_filter
trade sides: long + short
initial exits: SL4 ATR / TP10 ATR
```

Interpretation:

```text
More trades.
Noisier.
Historically long side was stronger than short side in fixed TP mode.
Becomes interesting only when runner management unlocks large tails.
```

## Prior findings recap

### BE / protected branch

Naive hard BE at entry is not accepted as the current protective formula.

Findings:

```text
ADX/DI protected events were side-aligned.
ADX/DI selected high-quality trades.
But hard BE often closed after large MFE had already happened.
```

Current interpretation:

```text
ADX/DI is not primarily a BE trigger.
ADX/DI is a candidate runner activation signal.
```

### Runner branch

Phase 1 tested:

```text
ADX/DI -> runner
runner -> disable initial TP
RSI 5m signal exit as dynamic overheat exit
```

Important limitation:

```text
rsi_signal_exit is currently an exit_policy signal, not phase-gated runtime_exit.
Therefore some RSI exits can happen before runner.
```

Even with that limitation, the RSI 5m 90/10 runner variants were strongly positive.

## Current working hypothesis

```text
EMA200 entry edge creates many mediocre fixed-TP trades and a small number of large runner opportunities.
ADX/DI identifies the runner subset.
Disabling initial TP lets runner trades avoid premature fixed TP.
RSI 5m 90/10 can act as a late overheat/exhaustion exit.
```

## Main unresolved questions

1. Fee model: current runs used `fees_rate = 0.0006` one-way. That may be too conservative for Bybit futures research.
2. Causality: current summary is not paired causal comparison. It shows aggregate run behavior.
3. Phase gating: RSI signal exits are not guaranteed to occur only after runner.
4. Outliers: top money variants may be driven by a small runner cohort; verify yearly distribution and individual runner trades before broadening the grid.
5. Exit model: RSI 90/10 is promising but probably not the final only runner exit. EMA loss-of-momentum / very-fast EMA exits should be tested after fee rerun.
