# RSI 1h Edge Discovery - Phase 2B Final Findings

## Status

Corrected Phase 2B completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase2b_corrected_width_stability_fee04
candidates: 81
ok: 81
failed: 0
duration_sec: 2266.0
```

This is the corrected Phase 2B batch:

```text
w10 / w11 / w12
r11 / r12 / r13
lb10 / lb20 / lb35
rails 2.15 / 2.35 / 2.45
```

## What Phase 2B confirmed

Phase 2B confirms that the real center of the width edge is:

```text
current_width = w11
```

Phase 2A suggested that lb20 was more stable than lb10. Phase 2B refines that:

```text
lb10:
  sharp peak

lb20:
  stability baseline

lb35:
  slower comparator, still alive but not better than lb20
```

Most important correction:

```text
recent_width <= current_width is often redundant.
```

For example, with `w11/r11`, `recent_max_width >= 11` is mostly guaranteed by the current width passing `w11`.

So the meaningful recent-width checks are:

```text
w11/r12
w11/r13
```

The main non-redundant core is:

```text
w11/r12
```

## Aggregates by current width

| w | mean PF | median PF | mean PnL | mean WR | mean trades | PF>=1.15 | both PF>1 | mean gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w10 | 1.087 | 1.101 | 2 257 | 55.2% | 253 | 1 | 13 | 0.211 |
| w11 | 1.171 | 1.175 | 3 433 | 56.6% | 198 | 24 | 26 | 0.077 |
| w12 | 1.053 | 1.051 | 654 | 53.9% | 144 | 0 | 2 | 0.257 |

Interpretation:

```text
w10:
  broad/profit lane, but often short-heavy

w11:
  confirmed main ridge

w12:
  too strict for the main baseline; trade count drops and long side often breaks
```

## Aggregates by width lookback

| lb | mean PF | median PF | mean PnL | mean WR | PF>=1.15 | both PF>1 | mean gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lb10 | 1.102 | 1.091 | 2 003 | 55.3% | 6 | 12 | 0.199 |
| lb20 | 1.109 | 1.109 | 2 260 | 55.3% | 10 | 15 | 0.178 |
| lb35 | 1.101 | 1.101 | 2 080 | 55.2% | 9 | 14 | 0.169 |

Interpretation:

```text
lb10:
  sharp peak

lb20:
  best stability center

lb35:
  acceptable slow comparator, but does not beat lb20
```

## Stable non-redundant shortlist

Selection criteria used here:

```text
both long PF and short PF > 1
recent_width > current_width
trades >= 190
PF >= 1.15
WR >= 56.4%
```

Stability score prioritizes:

```text
30% win rate
25% PF symmetry
25% trade count
20% total PF
```

| rank | candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| 2 | 2.35 w11/r12/lb20 | 199 | 4 009 | 1.190 | 56.8% | -25.0% | 1.191 | 1.189 | 0.001 |
| 3 | 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| 4 | 2.35 w11/r12/lb10 | 196 | 4 312 | 1.205 | 57.1% | -23.6% | 1.222 | 1.187 | 0.035 |
| 5 | 2.35 w11/r12/lb35 | 202 | 3 511 | 1.167 | 56.4% | -25.0% | 1.163 | 1.173 | 0.010 |
| 6 | 2.15 w11/r12/lb35 | 203 | 3 191 | 1.170 | 56.7% | -20.9% | 1.153 | 1.189 | 0.036 |
| 7 | 2.15 w11/r13/lb20 | 193 | 3 192 | 1.179 | 57.0% | -20.3% | 1.204 | 1.152 | 0.052 |
| 8 | 2.45 w11/r12/lb20 | 199 | 3 862 | 1.178 | 56.8% | -25.8% | 1.206 | 1.146 | 0.060 |
| 9 | 2.45 w11/r12/lb35 | 202 | 3 351 | 1.155 | 56.4% | -25.8% | 1.178 | 1.130 | 0.049 |
| 10 | 2.45 w11/r12/lb10 | 196 | 4 174 | 1.192 | 57.1% | -24.4% | 1.238 | 1.145 | 0.093 |
| 11 | 2.15 w11/r13/lb35 | 198 | 3 104 | 1.171 | 56.6% | -20.9% | 1.221 | 1.118 | 0.103 |

## Selected candidates to carry forward

| tag | candidate | trades | PnL | PF | WR | DD | long PF | short PF | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primary_stability_baseline | 2.15 w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 | 0.040 |
| sharp_core_best_score | 2.15 w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 | 0.008 |
| upper_semantic_balanced | 2.35 w11/r12/lb20 | 199 | 4 009 | 1.190 | 56.8% | -25.0% | 1.191 | 1.189 | 0.001 |
| upper_semantic_pnl | 2.35 w11/r12/lb10 | 196 | 4 312 | 1.205 | 57.1% | -23.6% | 1.222 | 1.187 | 0.035 |
| transition_stability_comparator | 2.45 w11/r12/lb20 | 199 | 3 862 | 1.178 | 56.8% | -25.8% | 1.206 | 1.146 | 0.060 |
| transition_sharp_comparator | 2.45 w11/r12/lb10 | 196 | 4 174 | 1.192 | 57.1% | -24.4% | 1.238 | 1.145 | 0.093 |
| balanced_but_recent_redundant | 2.45 w11/r11/lb20 | 203 | 3 787 | 1.175 | 56.7% | -25.8% | 1.176 | 1.174 | 0.002 |
| profit_lane_not_main | 2.45 w10/r11/lb20 | 271 | 4 474 | 1.153 | 56.1% | -22.6% | 1.012 | 1.343 | 0.331 |

## Final candidate roles

### Main stability baseline

```text
2.15 + w11/r12/lb20
```

Reason:

```text
non-redundant recent width
lb20 stability center
200 trades
PF 1.202
WR 57.5%
long PF 1.184
short PF 1.224
maxDD -20.3%
```

### Sharp core

```text
2.15 + w11/r12/lb10
```

Reason:

```text
best metric-stable point
PF 1.218
WR 57.9%
PF symmetry gap only 0.008
```

Use it as a sharp comparator, not the only baseline.

### Best PF-symmetric upper semantic comparator

```text
2.35 + w11/r12/lb20
```

Reason:

```text
long PF 1.191
short PF 1.189
PF symmetry gap 0.001
PF 1.190
PnL +4 009
```

### Upper semantic PnL comparator

```text
2.35 + w11/r12/lb10
```

Reason:

```text
PnL +4 312
PF 1.205
WR 57.1%
```

But maxDD is worse than 2.15.

### Transition comparator

```text
2.45 + w11/r12/lb20
```

Reason:

```text
uses lb20 stability logic
PF 1.178
PnL +3 862
long PF 1.206
short PF 1.146
```

It is useful, but not the main baseline.

### Profit lane, not main

```text
2.45 + w10/r11/lb20
```

Reason:

```text
highest PnL: +4 474
many trades: 271
```

But:

```text
long PF 1.012
short PF 1.343
PF gap 0.331
```

This is short-heavy. Keep as comparator, not as the main strategy core.

## Final Phase 2B conclusion

```text
Width discovery is now good enough to close the entry-core stage.
```

Carry forward:

```text
Main baseline:
  2.15 + w11/r12/lb20

Sharp comparator:
  2.15 + w11/r12/lb10

Upper semantic comparator:
  2.35 + w11/r12/lb20
  2.35 + w11/r12/lb10

Transition comparator:
  2.45 + w11/r12/lb20
  2.45 + w11/r12/lb10

Profit-lane comparator:
  2.45 + w10/r11/lb20
```

Do not carry forward as main:

```text
w12:
  too strict, low trade count, long side often breaks

r11 with w11:
  balanced but recent-width condition is redundant

w10 profit lanes:
  useful comparator, but short-heavy
```

## Recommended next step

Do not sweep width again immediately.

Next phase should use the selected candidates only:

```text
Phase 3:
  RSI 1h diagnostics / blocker over the fixed width core
```

Suggested fixed cores:

```text
A. main stability baseline:
   2.15 + w11/r12/lb20

B. sharp comparator:
   2.15 + w11/r12/lb10

C. upper semantic:
   2.35 + w11/r12/lb20

D. transition comparator:
   2.45 + w11/r12/lb20
```

Still avoid:

```text
ADX runner
BE / lock
runtime exits
partial TP
trailing
HTF context
asymmetric rails
```

until RSI 1h diagnostics are understood.
