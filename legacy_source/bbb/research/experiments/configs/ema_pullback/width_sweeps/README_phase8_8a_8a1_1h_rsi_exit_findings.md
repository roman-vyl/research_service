# Phase 8 / 8A / 8A.1 — 1h RSI Exit Findings

## Scope

This README summarizes Phase 8, Phase 8A, and especially Phase 8A.1 for the **1h RSI exit layer**.

The purpose of the test was not to prove that a fixed RSI take-profit is the final exit strategy. The purpose was to decompose the exit problem and test one layer in isolation:

```text
entry logic
+ initial ATR stop
+ far ATR safety TP
+ one tested 1h RSI exit
```

This is a synthetic diagnostic setup. In the future the real strategy may combine several layers:

```text
EMA trailing / loss-of-momentum
RSI overheat
break-even stop
runner / profile-specific exits
```

So Phase 8A.1 should be read as an **exit-layer diagnostic**, not as a final combined strategy result.

## Phase definitions

### Phase 8

General transition from fixed ATR take-profit measurement to dynamic exits.

Phase 7A showed that a meaningful MFE tail exists, but fixed ATR TP is only a measurement ruler. Phase 8 starts testing mechanisms that may capture that movement dynamically.

### Phase 8A

RSI overheat exit research.

Goal:

```text
Does RSI detect useful overheat points?
Does it preserve enough MFE?
Does it reduce high-MFE / low-capture failures?
Does it exit too early or too late?
```

### Phase 8A.1

1h RSI extreme continuation.

Tested thresholds:

```text
1h RSI 80/20
1h RSI 85/15
1h RSI 90/10
```

Thresholds are symmetric by design:

```text
long exits above X
short exits below 100 - X
```

We intentionally do **not** tune long and short separately based on a five-year BTC up-cycle.

## Baselines

### Relaxed

```text
EMA stack: 100 / 200 / 496
width: current 9 ATR, recent 10 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 4 ATR
Safety TP: 40 ATR
```

### Strict

```text
EMA stack: 100 / 200 / 496
width: current 12 ATR, recent 14 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 6 ATR
Safety TP: 40 ATR
```

## Important metric definitions

### “Big move” / high MFE

The report uses the v6 trade-quality config:

```text
high_mfe_pct_fallback = 0.02
```

So in this README, “big move” means approximately:

```text
trade reached at least ~2% MFE
```

The count is approximated from:

```text
high_mfe_high_capture + high_mfe_low_capture
```

This tells us how many trades produced a meaningful favorable excursion, regardless of whether the strategy captured it.

### “Successfully stretched to high MFE”

This is approximated by:

```text
high_mfe_high_capture
```

This tells us how many trades both reached high MFE and captured a meaningful part of it.

### “Failed capture”

This is approximated by:

```text
high_mfe_low_capture
```

This tells us how many trades had a meaningful favorable move but gave it back.

## Relaxed branch results

| Exit | Trades | PF | PnL | Winrate | DD | Avg hold bars | P75 MFE | P90 MFE | Big-move trades | Successfully captured big move | RSI signal exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 319 | 1.182 | +4271 | 12.9% | -31.7% | 317 | 2.61% | 5.14% | 94 / 29.5% | 38 / 11.9% | 0 |
| 1h RSI 80/20 | 334 | 1.044 | +867 | 17.1% | -32.6% | 163 | 2.48% | 4.44% | 94 / 28.1% | 46 / 13.8% | 38 |
| 1h RSI 85/15 | 331 | 1.095 | +2092 | 14.8% | -32.8% | 216 | 2.54% | 5.06% | 94 / 28.4% | 41 / 12.4% | 20 |
| 1h RSI 90/10 | 325 | 1.183 | +4268 | 13.8% | -29.3% | 240 | 2.56% | 5.11% | 95 / 29.2% | 41 / 12.6% | 8 |

### Relaxed interpretation

The relaxed branch shows a clear gradient:

```text
80/20: active, still too early
85/15: better, but still below control
90/10: almost equal to control and preserves the MFE tail
```

Key observations:

```text
Control big-move share: 29.5%
RSI 80/20 big-move share: 28.1%
RSI 85/15 big-move share: 28.4%
RSI 90/10 big-move share: 29.2%
```

The percentage of trades that produced a big move stayed remarkably stable, around **28–30%**. That is the most important diagnostic result: the entry layer is capable of producing a high-MFE tail in roughly one third of trades.

The difference is capture quality and timing:

```text
Control successfully captured big move: 11.9%
RSI 80/20 successfully captured big move: 13.8%
RSI 85/15 successfully captured big move: 12.4%
RSI 90/10 successfully captured big move: 12.6%
```

RSI 80/20 produced many signal exits, but it reduced p90 MFE. RSI 90/10 preserved p90 MFE and nearly matched control PF/PnL, but it only fired 8 times. That means 1h RSI 90/10 is a rare overheat cap, not a general exit system.

## Strict branch results

| Exit | Trades | PF | PnL | Winrate | DD | Avg hold bars | P75 MFE | P90 MFE | Big-move trades | Successfully captured big move | RSI signal exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 133 | 1.352 | +3398 | 18.8% | -19.3% | 314 | 3.16% | 5.26% | 41 / 30.8% | 21 / 15.8% | 0 |
| 1h RSI 80/20 | 135 | 1.157 | +1349 | 22.2% | -19.6% | 237 | 2.82% | 4.34% | 41 / 30.4% | 24 / 17.8% | 15 |
| 1h RSI 85/15 | 135 | 1.171 | +1517 | 20.7% | -19.3% | 253 | 2.82% | 4.82% | 40 / 29.6% | 22 / 16.3% | 8 |
| 1h RSI 90/10 | 134 | 1.186 | +1711 | 19.4% | -19.3% | 268 | 2.99% | 5.11% | 40 / 29.9% | 21 / 15.7% | 2 |

### Strict interpretation

The strict branch is cleaner but less tolerant of RSI exits.

Control remains the strongest version by total PF/PnL:

```text
Strict control PF: 1.352
Strict control PnL: +3398
```

RSI exits reduce holding time and still produce high-quality signal exits, but none of the tested 1h thresholds beats control as a standalone layer.

The big-move rate is again stable:

```text
Control big-move share: 30.8%
RSI 80/20 big-move share: 30.4%
RSI 85/15 big-move share: 29.6%
RSI 90/10 big-move share: 29.9%
```

This again suggests that the entry logic regularly creates meaningful MFE, but a 1h RSI exit alone is not enough to capture it optimally.

## RSI signal-exit quality

| Branch | Exit | RSI signal exits | Signal PnL | Signal winrate | Signal avg return | Signal avg hold bars | Signal winners / failures |
|---|---|---:|---:|---:|---:|---:|---:|
| relaxed | 1h RSI 80/20 | 38 | +11750 | 94.7% | 3.30% | 456 | 31 / 1 |
| relaxed | 1h RSI 85/15 | 20 | +9081 | 95.0% | 4.51% | 971 | 15 / 0 |
| relaxed | 1h RSI 90/10 | 8 | +5698 | 100.0% | 6.98% | 1967 | 7 / 0 |
| strict | 1h RSI 80/20 | 15 | +4264 | 100.0% | 2.91% | 658 | 13 / 0 |
| strict | 1h RSI 85/15 | 8 | +1971 | 100.0% | 2.42% | 758 | 5 / 0 |
| strict | 1h RSI 90/10 | 2 | +286 | 100.0% | 1.43% | 200 | 1 / 0 |

The RSI signal exits themselves are high quality. This is important.

The problem is not that RSI overheat is useless. The problem is that RSI as the **only** dynamic exit layer cannot solve all exit cases:

```text
RSI catches rare/clear overheat.
RSI does not manage normal loss-of-momentum.
RSI does not protect all trades that had MFE but later gave it back.
RSI does not replace EMA trailing or break-even management.
```

## What percentage of trades gave a real large move?

Across the 1h RSI extreme runs:

### Relaxed

```text
Control:  94 / 319 = 29.5%
80/20:    94 / 334 = 28.1%
85/15:    94 / 331 = 28.4%
90/10:    95 / 325 = 29.2%
```

### Strict

```text
Control:  41 / 133 = 30.8%
80/20:    41 / 135 = 30.4%
85/15:    40 / 135 = 29.6%
90/10:    40 / 134 = 29.9%
```

Conclusion:

```text
Roughly 28–31% of trades produce a genuinely meaningful favorable move.
```

This is the most useful Phase 8A.1 diagnostic insight.

The strategy does not need every entry to become a runner. It needs an exit-management stack that can recognize and protect the top ~30% of trades without destroying the rest.

## What percentage was successfully captured?

### Relaxed

```text
Control:  38 / 319 = 11.9%
80/20:    46 / 334 = 13.8%
85/15:    41 / 331 = 12.4%
90/10:    41 / 325 = 12.6%
```

### Strict

```text
Control:  21 / 133 = 15.8%
80/20:    24 / 135 = 17.8%
85/15:    22 / 135 = 16.3%
90/10:    21 / 134 = 15.7%
```

Conclusion:

```text
Only about 12–18% of all trades both reach high MFE and capture it well.
```

This is the core gap:

```text
~30% of trades produce a large move,
but only ~12–18% capture it well.
```

That gap is exactly what EMA trailing, break-even, and context-aware runner exits need to attack.

## Main Phase 8A.1 conclusions

### 1. 1h RSI 80/20 is still too active

It catches real profitable exits, but it cuts too much of the MFE tail.

Relaxed 80/20:

```text
signal exits: 38
p90 MFE: 4.44%
control p90 MFE: 5.14%
```

Strict 80/20:

```text
signal exits: 15
p90 MFE: 4.34%
control p90 MFE: 5.26%
```

### 2. 1h RSI 85/15 is a middle layer, but still not enough

It improves the timing compared to 80/20, but does not beat control as a standalone exit.

### 3. 1h RSI 90/10 is a rare overheat cap

It preserves the MFE tail best but fires rarely.

Relaxed 90/10:

```text
signal exits: 8
signal winrate: 100.0%
signal avg return: 6.98%
```

Strict 90/10:

```text
signal exits: 2
signal winrate: 100.0%
signal avg return: 1.43%
```

This is useful as a rare overheat component, not as a main exit engine.

### 4. 1h RSI is not the primary answer

1h RSI is useful, but insufficient:

```text
good as:    late overheat cap / diagnostic signal
bad as:     only dynamic exit layer
missing:    loss-of-momentum logic, trailing logic, protective management
```

## Decision after Phase 8A.1

Do not spend more time sweeping 1h RSI thresholds.

Current classification:

```text
1h 65/70/75: too early, rejected for runner-exit
1h 80/20: useful but still too active
1h 85/15: middle, not enough
1h 90/10: rare overheat cap candidate
```

Carry forward:

```text
optional auxiliary RSI overheat:
  1h RSI 90/10
  possibly 1h RSI 85/15 as a less strict alternative
```

Primary next research should move to:

```text
EMA trailing / EMA loss-of-momentum exits
break-even after first favorable movement
context-aware runner management
```

## Final takeaway

Phase 8A.1 shows that the entry logic has real potential:

```text
~28–31% of trades create a meaningful favorable move.
```

But the current capture rate is lower:

```text
~12–18% of all trades both reach high MFE and capture it well.
```

So the next problem is not “find another fixed take-profit”. The next problem is:

```text
build exit management that protects and harvests the top ~30% of trades
without over-cutting the runner tail.
```
