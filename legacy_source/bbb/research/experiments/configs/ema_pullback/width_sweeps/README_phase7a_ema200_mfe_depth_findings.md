# Phase 7A — EMA200 MFE Depth Diagnostic Findings

## Purpose

Phase 7A was a measurement phase, not a final exit-policy phase.

The large ATR take-profit values were used as a diagnostic ruler so trades stayed open long enough for schema v6 `path_diagnostics_summary` to measure MFE/MAE inside the real executed trade window:

```text
entry_idx .. exit_idx inclusive
```

No post-exit bars. No shadow trades. No hypothetical continuation.

Worsening PF/winrate at TP20/TP30/TP40 is not the conclusion that these fixed ATR take-profits should be traded. They are only a ruler for exposing the favorable-excursion tail.

## Branches

### Relaxed diagnostic branch

```text
EMA stack: 100 / 200 / 496
width: current 9 ATR, recent 10 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 4 ATR
TP diagnostic ruler: 20 / 30 ATR
```

### Strict diagnostic branch

```text
EMA stack: 100 / 200 / 496
width: current 12 ATR, recent 14 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 6 ATR
TP diagnostic ruler: 24 / 30 ATR
```

## Core MFE table

| Branch | TP ruler | Trades | Median MFE | P75 MFE | P90 MFE | Median bars to MFE |
|---|---:|---:|---:|---:|---:|---:|
| Relaxed | TP20 | 345 | 0.69% | 2.12% | 3.50% | 26.0 |
| Relaxed | TP30 | 330 | 0.71% | 2.52% | 4.62% | 27.0 |
| Strict | TP24 | 137 | 0.82% | 2.52% | 3.51% | 36.0 |
| Strict | TP30 | 136 | 0.82% | 2.78% | 3.94% | 37.5 |

## Main MFE conclusions

### 1. The favorable-excursion tail exists

The practical measured target zones are:

```text
normal good bounce:      ~2.0% to 2.8% MFE
strong tail:             ~3.5% to 4.6% MFE
rare best movements:     need full trade_records beyond p90 summary
```

This supports dynamic exits rather than fixed ATR take-profit as the final profit-capture mechanism.

### 2. Relaxed TP30 is the best diagnostic sensor

```text
Relaxed TP30:
  p75 MFE = 2.52%
  p90 MFE = 4.62%
  trades  = 330
```

It is not necessarily the best final strategy. It is the best measurement lens for high-MFE and failed-capture cases.

### 3. Strict TP30 is cleaner but smaller

```text
Strict TP30:
  p75 MFE = 2.78%
  p90 MFE = 3.94%
  trades  = 136
```

Strict is likely a better future production-entry baseline; relaxed is better for exploratory diagnostics.

## Timing conclusions

Overall median bars to MFE are relatively low:

```text
Relaxed TP20: 26.0 bars
Relaxed TP30: 27.0 bars
Strict TP24:  36.0 bars
Strict TP30:  37.5 bars
```

On 5m this is roughly 2–3 hours for the median trade-level MFE.

True runner winners take much longer:

| Branch | TP ruler | Take-profit median bars to MFE |
|---|---:|---:|
| Relaxed | TP20 | 132.5 |
| Relaxed | TP30 | 264.0 |
| Strict | TP24 | 122.5 |
| Strict | TP30 | 142.5 |

Conclusion:

```text
quick exits can capture normal bounces;
runner exits need a different holding regime.
```

## MAE conclusions

The best winner group does not usually require large adverse movement.

Take-profit group median / p90 MAE:

| Branch | TP ruler | Median MAE | P90 MAE |
|---|---:|---:|---:|
| Relaxed | TP20 | 0.29% | 0.67% |
| Relaxed | TP30 | 0.29% | 0.68% |
| Strict | TP24 | 0.30% | 0.73% |
| Strict | TP30 | 0.28% | 0.71% |

This supports protective management, but break-even should be tested after signal exits because too-early BE may kill runners.

## Failed-capture conclusion

The stop-loss group still shows meaningful MFE in its upper tail:

| Branch | TP ruler | Stop-loss p90 MFE |
|---|---:|---:|
| Relaxed | TP20 | 2.14% |
| Relaxed | TP30 | 2.82% |
| Strict | TP24 | 1.92% |
| Strict | TP30 | 2.73% |

A meaningful subset of trades moved favorably and then gave the movement back into SL. These are the main targets for dynamic exit research.

## Short-side interpretation

Short deterioration at larger TP is not proof that short logic is broken. The five-year BTC sample has a strong upward-trend bias. Larger TP values require long directional continuation, and the historical sample contained fewer long-duration short continuations.

Short still has measurable MFE:

```text
Relaxed TP30 short p90 MFE = 4.06%
Strict TP30 short p90 MFE  = 3.82%
```

Interpretation:

```text
short can produce impulse;
short may need faster capture / tighter management than long on this BTC sample.
```

## Phase 7A final decision

Do not keep expanding fixed ATR TP.

Proceed to Phase 8:

1. 1h RSI overheat exits.
2. EMA trailing / EMA loss-of-momentum exits.
3. Break-even stop integration after signal exits are understood.

Phase 8 runs should keep a far ATR TP only as a safety cap, not as the primary profit-taking mechanism.
