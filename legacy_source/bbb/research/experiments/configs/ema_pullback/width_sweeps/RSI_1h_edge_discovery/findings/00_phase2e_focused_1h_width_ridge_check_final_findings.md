# RSI 1h Edge Discovery - Phase 2E Final Findings

## Status

Phase 2E completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase2e_focused_1h_width_ridge_check_fee04
created_at: 2026-06-16T20:35:19Z
candidates: 113
ok: 113
failed: 0
duration_sec: 4163.4
```

## Research question

Phase 2E checked whether the Phase 2D 1h-width candidate was a real stable ridge:

```text
1h 2.15 w2.25/r2.75/lb35
```

Objective:

```text
symmetric long/short PF
enough trades
visible EMA200 bounce semantics
main rail 2.15 preferred
no 2.45 transition rail
```

## Executive conclusion

Phase 2E confirms that the 1h-width ridge is real.

The strongest accepted 1h-width candidate by our main score is:

```text
1h 2.15 w2.2/r2.75/lb35
```

Metrics:

```text
trades: 163
PnL: +4 679
PF: 1.279
WR: 58.3%
DD: -15.8%
long PF: 1.222
short PF: 1.402
PF gap: 0.180
```

The most symmetric accepted 1h-width point is:

```text
1h 2.15 w1.9/r2.75/lb35
```

Metrics:

```text
trades: 167
PnL: +3 853
PF: 1.222
WR: 57.5%
DD: -17.7%
long PF: 1.174
short PF: 1.318
PF gap: 0.144
```

Interpretation:

```text
w2.2/w2.25/w2.3 + r2.75 + lb35:
  best performance-symmetry compromise.

w1.9/w2.0/w2.1 + r2.75 + lb35:
  cleaner symmetry, lower PF/PnL.

w2.0 + r2.75 + lb20:
  performance branch, but too short-dominant for main symmetric strategy.
```

## Important comparison with base core

The base-width reference is still the cleanest pure symmetry candidate:

```text
base 2.15 w11/r12/lb10

trades: 197
PnL: +4 088
PF: 1.218
WR: 57.9%
DD: -20.3%
long PF: 1.214
short PF: 1.222
PF gap: 0.008
```

So this is not a replacement. It is a two-lane shortlist.

```text
Lane A - base ATR width:
  cleanest symmetric local EMA200 bounce core

Lane B - 1h ATR width:
  stronger performance ridge, but more short-tilted
```

## Group summary

| group | n | median PF | mean PF | max PF | median PnL | max PnL | mean WR | mean trades | accepted | strict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control_1h | 2 | 1.243 | 1.243 | 1.279 | 4 224 | 4 679 | 57.8% | 166 | 2 | 1 |
| control_base | 3 | 1.202 | 1.204 | 1.218 | 4 009 | 4 088 | 57.4% | 199 | 2 | 2 |
| focused_1h | 108 | 1.194 | 1.204 | 1.435 | 3 022 | 6 816 | 57.2% | 162 | 26 | 8 |

## Rail 2.15 by current width

| current | n | median PF | max PF | mean PnL | max PnL | mean WR | mean trades | accepted | strict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.9 | 9 | 1.152 | 1.382 | 2 496 | 5 452 | 56.5% | 166 | 1 | 1 |
| 2 | 9 | 1.152 | 1.382 | 2 415 | 5 452 | 56.4% | 165 | 1 | 1 |
| 2.1 | 9 | 1.152 | 1.382 | 2 548 | 5 452 | 56.5% | 165 | 1 | 1 |
| 2.2 | 9 | 1.185 | 1.382 | 2 937 | 5 452 | 57.1% | 161 | 2 | 2 |
| 2.25 | 9 | 1.193 | 1.382 | 3 045 | 5 452 | 57.2% | 160 | 2 | 1 |
| 2.3 | 9 | 1.193 | 1.382 | 3 233 | 5 452 | 57.2% | 160 | 3 | 2 |

## Accepted candidates

Acceptance gate:

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.12
short PF > 1.12
PF gap <= 0.30
```

Strict symmetric target:

```text
PF gap <= 0.20
rail = 2.15
```

| rank | candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1h 2.35 w2.2/r2.65/lb20 | 171 | 5 076 | 1.268 | 59.6% | -19.0% | 1.280 | 1.247 | 0.033 |
| 2 | 1h 2.35 w2.25/r2.65/lb20 | 171 | 5 076 | 1.268 | 59.6% | -19.0% | 1.280 | 1.247 | 0.033 |
| 3 | base 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| 4 | 1h 2.35 w2.3/r2.65/lb20 | 170 | 6 550 | 1.364 | 60.0% | -19.0% | 1.288 | 1.534 | 0.247 |
| 5 | base 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| 6 | 1h 2.35 w2.2/r2.75/lb35 | 162 | 6 331 | 1.345 | 59.3% | -17.3% | 1.283 | 1.477 | 0.194 |
| 7 | 1h 2.35 w2.25/r2.75/lb35 | 162 | 6 331 | 1.345 | 59.3% | -17.3% | 1.283 | 1.477 | 0.194 |
| 8 | 1h 2.35 w2.3/r2.75/lb35 | 162 | 6 331 | 1.345 | 59.3% | -17.3% | 1.283 | 1.477 | 0.194 |
| 9 | 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| 10 | 1h 2.15 w2.2/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| 11 | 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| 12 | 1h 2.15 w2.3/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| 13 | 1h 2.35 w1.9/r2.65/lb20 | 172 | 4 421 | 1.229 | 59.3% | -22.3% | 1.278 | 1.147 | 0.131 |
| 14 | 1h 2.35 w2/r2.65/lb20 | 172 | 4 421 | 1.229 | 59.3% | -22.3% | 1.278 | 1.147 | 0.131 |
| 15 | 1h 2.35 w2.1/r2.65/lb20 | 172 | 4 421 | 1.229 | 59.3% | -22.3% | 1.278 | 1.147 | 0.131 |
| 16 | 1h 2.35 w1.9/r2.75/lb35 | 166 | 5 332 | 1.279 | 58.4% | -17.3% | 1.232 | 1.376 | 0.144 |
| 17 | 1h 2.35 w2/r2.75/lb35 | 166 | 5 332 | 1.279 | 58.4% | -17.3% | 1.232 | 1.376 | 0.144 |
| 18 | 1h 2.35 w2.1/r2.75/lb35 | 166 | 5 332 | 1.279 | 58.4% | -17.3% | 1.232 | 1.376 | 0.144 |

## Selected roles

| role | candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base_symmetric_reference | base 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| base_stability_reference | base 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| phase2d_1h_control | 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| best_1h_strict_score | 1h 2.15 w2.2/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| most_symmetric_1h_accepted | 1h 2.15 w1.9/r2.75/lb35 | 167 | 3 853 | 1.222 | 57.5% | -17.7% | 1.174 | 1.318 | 0.144 |
| performance_1h_not_main | 1h 2.15 w1.9/r2.75/lb20 | 150 | 5 452 | 1.382 | 59.3% | -17.1% | 1.217 | 1.857 | 0.640 |
| upper_comparator_not_main | 1h 2.35 w2.3/r2.65/lb20 | 170 | 6 550 | 1.364 | 60.0% | -19.0% | 1.288 | 1.534 | 0.247 |

## Heatmaps

Heatmaps are stored under:

```text
charts/phase2e/heatmaps/
```

Most important heatmaps:

```text
heatmap_rail2p15_lb35_profit_factor.png
heatmap_rail2p15_lb35_pnl.png
heatmap_rail2p15_lb35_pf_symmetry_gap.png
heatmap_rail2p15_lb35_long_profit_factor.png
heatmap_rail2p15_lb35_short_profit_factor.png
heatmap_rail2p15_lb35_trades.png
heatmap_rail2p15_alllb_mean_profit_factor.png
heatmap_rail2p15_alllb_mean_pf_symmetry_gap.png
```

## Ridge interpretation

The best semantic pocket is centered around:

```text
rail: 2.15
recent_width_1h: 2.75
current_width_1h: 1.9 - 2.3
lookback: lb35
```

The heatmaps show a real ridge, not one isolated point. The strongest accepted points are flat / repeated across neighboring current-width thresholds because the actual entry set does not change until threshold crosses the next discrete width boundary.

## Best candidates to keep before blockers / exit management

### Candidate A - clean base reference

```text
base 2.15 w11/r12/lb10
```

Use as clean symmetric local EMA200 bounce reference.

### Candidate B - main 1h-width performance/symmetry candidate

```text
1h 2.15 w2.2/r2.75/lb35
```

Use as main 1h-width candidate for further testing.

### Candidate C - more symmetric 1h-width candidate

```text
1h 2.15 w1.9/r2.75/lb35
```

Use as stricter symmetry comparator.

### Candidate D - 1h-width performance candidate, not main

```text
1h 2.15 w1.9/r2.75/lb20
```

Metrics:

```text
trades: 150
PnL: +5 452
PF: 1.382
WR: 59.3%
long PF: 1.217
short PF: 1.857
gap: 0.640
```

Keep it, but do not use as main symmetric strategy because short side dominates.

## Decision

Carry forward both lanes:

```text
A. Base-width symmetric local bounce:
   base 2.15 w11/r12/lb10
   base 2.15 w11/r12/lb20

B. 1h-width performance/symmetric bounce:
   1h 2.15 w2.2/r2.75/lb35

C. 1h-width stricter symmetry comparator:
   1h 2.15 w1.9/r2.75/lb35

D. 1h-width performance comparator:
   1h 2.15 w1.9/r2.75/lb20
```

## Next step

Now it is acceptable to start blocker / exit-management tests, but only on the preserved shortlist.

Suggested next phase:

```text
Phase 3A:
  RSI 1h diagnostic segmentation
```

Do not immediately add an active blocker across all candidates.

First segment the saved candidates by RSI 1h state:

```text
base 2.15 w11/r12/lb10
base 2.15 w11/r12/lb20
1h 2.15 w2.2/r2.75/lb35
1h 2.15 w1.9/r2.75/lb35
1h 2.15 w1.9/r2.75/lb20
```

Goal:

```text
Find whether RSI 1h explains losing clusters without destroying long/short symmetry.
```
