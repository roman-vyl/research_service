# RSI 1h Edge Discovery - Phase 2D Broad 1h Width Discovery Findings

## Status

Phase 2D completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase2d_broad_1h_width_discovery_fee04
candidates: 187
ok: 187
failed: 0
duration_sec: 8758.1
```

## What Phase 2D tested

This was a broad candidate discovery in `width / ATR_1h` coordinates.

It was not strict coordinate mapping from base `w11/r12`. The goal was practical:

```text
Can 1h ATR width produce a useful EMA200-bounce-like candidate,
without immediately drifting into higher-order trend capture?
```

The main rail was `2.15`.  
`2.35` was an upper comparator.  
`2.45` was only a small transition tail.

## Executive conclusion

Phase 2D found a real usable 1h-width candidate.

The best main-rail bounce candidate is:

```text
1h 2.15 w2/r2.75/lb20
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

It passes the Phase 2D acceptance gate:

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.10
short PF > 1.10
PF gap <= 0.35
```

But it is still more short-tilted than the base sharp core.

The base sharp core remains the cleanest balanced reference:

```text
base 2.15 w11/r12/lb10
PF 1.218
WR 57.9%
long PF 1.214
short PF 1.222
gap 0.008
```

So the result is not "replace base width completely".  
The correct result is:

```text
Lane A:
  base ATR width w11/r12 = balanced local pullback core

Lane B:
  1h ATR width around w2/r2.75 = valid 1h-width bounce candidate,
  stronger PnL/PF, but more short-tilted
```

## Group summary

| group | n | median PF | mean PF | max PF | median PnL | max PnL | mean WR | mean trades | accept |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base_control | 7 | 1.192 | 1.191 | 1.218 | 4 088 | 4 474 | 57.0% | 208 | 4 |
| broad_1h_width_main | 168 | 1.094 | 1.157 | 2.209 | 660 | 6 816 | 56.6% | 137 | 6 |
| transition_tail_1h_width | 12 | 1.321 | 1.309 | 1.523 | 4 123 | 8 439 | 59.0% | 126 | 1 |

## 1h width summary by current width

| w1h | n | median PF | max PF | mean PnL | max PnL | mean WR | mean trades | PF>=1.18 | accept |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w1.75 | 24 | 1.003 | 1.181 | 549 | 4 724 | 54.3% | 339 | 1 | 0 |
| w2 | 24 | 1.049 | 1.435 | 2 025 | 6 816 | 55.7% | 237 | 7 | 2 |
| w2.25 | 28 | 1.270 | 1.523 | 4 102 | 8 439 | 58.1% | 159 | 18 | 5 |
| w2.5 | 28 | 1.319 | 1.487 | 2 888 | 7 159 | 57.9% | 102 | 18 | 0 |
| w2.75 | 28 | 1.071 | 1.318 | 582 | 2 655 | 55.7% | 68 | 6 | 0 |
| w3 | 24 | 0.978 | 1.903 | -100 | 1 183 | 56.2% | 41 | 6 | 0 |
| w3.25 | 24 | 1.271 | 2.209 | 391 | 1 430 | 59.4% | 24 | 17 | 0 |

Interpretation:

```text
w1.75:
  too broad, mostly fee/noise heavy.

w2.0:
  main useful 1h-width zone.
  contains the best accepted 2.15 bounce candidate.

w2.25:
  good PnL pockets, but often weaker balance or short-side issues.

w2.5:
  strong branch seen already in Phase 2C, but more short/trend tilted.

w2.75+:
  trade count collapses or becomes unstable.
```

## Accepted candidates

These pass the declared Phase 2D acceptance gate:

```text
trades >= 120
PF >= 1.18
WR >= 57%
long PF > 1.10
short PF > 1.10
PF gap <= 0.35
```

| candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1h 2.45 w2.25/r2.75/lb35 | 162 | 7 891 | 1.413 | 60.5% | -17.7% | 1.385 | 1.470 | 0.084 |
| 1h 2.35 w2.25/r2.75/lb35 | 162 | 6 331 | 1.345 | 59.3% | -17.3% | 1.283 | 1.477 | 0.194 |
| base 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| 1h 2.35 w2/r2.75/lb35 | 166 | 5 332 | 1.279 | 58.4% | -17.3% | 1.232 | 1.376 | 0.144 |
| base 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| base 2.35 w11/r12/lb10 | 196 | 4 312 | 1.205 | 57.1% | -23.6% | 1.222 | 1.187 | 0.035 |
| 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| 1h 2.35 w2.25/r2.75/lb50 | 168 | 5 228 | 1.260 | 58.3% | -19.1% | 1.179 | 1.418 | 0.239 |
| 1h 2.15 w2/r2.75/lb35 | 167 | 3 853 | 1.222 | 57.5% | -17.7% | 1.174 | 1.318 | 0.144 |
| 1h 2.15 w2.25/r2.75/lb50 | 169 | 3 769 | 1.206 | 57.4% | -18.8% | 1.129 | 1.356 | 0.227 |
| base 2.45 w11/r12/lb10 | 196 | 4 174 | 1.192 | 57.1% | -24.4% | 1.238 | 1.145 | 0.093 |

## Selected roles

| role | candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base_reference_balanced | base 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| base_reference_sharp | base 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| balanced_1h_main_rail_leader | 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| profit_1h_main_rail_leader | 1h 2.15 w2/r2.75/lb20 | 150 | 5 452 | 1.382 | 59.3% | -17.1% | 1.217 | 1.857 | 0.640 |
| pf_1h_main_rail_leader | 1h 2.15 w2.25/r3/lb35 | 103 | 3 751 | 1.392 | 59.2% | -16.9% | 1.182 | 2.054 | 0.872 |
| low_dd_1h_main_rail_accepted | 1h 2.15 w2.25/r2.75/lb35 | 163 | 4 679 | 1.279 | 58.3% | -15.8% | 1.222 | 1.402 | 0.180 |
| high_sample_1h_main_rail_accepted | 1h 2.15 w2.25/r2.75/lb50 | 169 | 3 769 | 1.206 | 57.4% | -18.8% | 1.129 | 1.356 | 0.227 |
| upper_comparator_leader | 1h 2.35 w2.5/r2.75/lb35 | 141 | 6 231 | 1.444 | 60.3% | -21.4% | 1.273 | 1.937 | 0.665 |
| transition_tail_leader_not_main | 1h 2.45 w2.25/r2.75/lb20 | 149 | 8 439 | 1.523 | 61.1% | -17.7% | 1.396 | 1.863 | 0.467 |
| short_heavy_leader | 1h 2.45 w2.25/r2.75/lb20 | 149 | 8 439 | 1.523 | 61.1% | -17.7% | 1.396 | 1.863 | 0.467 |

## Candidate interpretation

### Main 1h-width candidate to carry forward

```text
1h 2.15 w2/r2.75/lb20
```

Why it matters:

```text
It is on the main 2.15 rail.
It has enough trades.
It improves PnL/PF versus the base sharp core.
It keeps both long and short profitable.
It does not require the 2.45 transition rail.
```

Caution:

```text
short PF is much stronger than long PF.
So this is not as symmetric as base w11/r12.
```

### Base core still matters

Keep:

```text
base 2.15 w11/r12/lb20
base 2.15 w11/r12/lb10
```

because they are still the cleanest balanced local EMA200 pullback references.

### 2.35 and 2.45 interpretation

`2.35` remains a useful upper comparator, but not the first main rail.

`2.45` should not become the main candidate just because PnL is high. It can represent higher-order trend capture rather than EMA200 bounce.

## Final Phase 2D decision

Choose:

```text
D. Need narrower follow-up around a discovered ridge.
```

The focused follow-up should center on:

```text
rail:
  2.15 primary
  2.35 comparator

current_width_1h:
  1.90
  2.00
  2.10
  2.20

recent_width_1h:
  2.65
  2.75
  2.85

lookback:
  lb10
  lb20
  lb35
```

Also preserve the base controls in the same batch.

## Next step

Phase 2E should be a focused ridge check around `1h 2.15 w2/r2.75/lb20`.

Do not add RSI yet.  
Do not add ADX/BE/runtime exits yet.

First confirm whether this 1h-width candidate is a stable ridge or a local pocket.
