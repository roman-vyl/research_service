# RSI 1h Edge Discovery — Phase 1B Findings

## Status

Phase 1B completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase1b_transition_width_check_fee04
candidates: 12
ok: 12
failed: 0
duration_sec: 373.2
```

## What Phase 1B tested

Phase 1B tested transition rails:

```text
2.45 / 2.45
2.50 / 2.50
```

on selected current widths from Phase 1A:

```text
w8, w9, w10, w11, w14, w16
```

Held constant:

```text
recent_width = r10
width_lookback = lb20
untouched75 / active8
fee = 0.04%
```

Still excluded:

```text
RSI
ADX
runtime exits
BE / lock
trailing
HTF context
asymmetric exits
```

## Executive summary

Phase 1B says:

```text
2.45 / 2.50 are not garbage.
They improve several selected widths versus the lower semantic rails.
But they are already transition rails, not the cleanest EMA200 semantic ruler.
```

The cleanest transition candidate is:

```text
2.45 + w11
```

because it keeps long and short almost perfectly balanced:

```text
trades: 203
PnL: +3 787
PF: 1.175
maxDD: -25.8%
long PF: 1.176
short PF: 1.174
```

The strongest raw transition candidate is:

```text
2.50 + w10
```

```text
trades: 278
PnL: +4 966
PF: 1.167
maxDD: -22.3%
long PF: 1.008
short PF: 1.379
```

But it is clearly short-heavy: most of the PnL comes from shorts.

The high-selectivity branch remains strong:

```text
2.50 + w16

trades: 49
PnL: +3 178
PF: 1.841
maxDD: -12.1%
long PF: 1.454
short PF: 2.253
```

But it is still only 49 trades, so it remains a separate robustness branch.

## Full Phase 1B result table

| Rail | Width | Trades | PnL | PF | Win rate | MaxDD | Long PF | Short PF | Long PnL | Short PnL | Bad ctx SL | Low MFE SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.45 | w8 | 411 | 2 954 | 1.063 | 55.5% | -38.4% | 1.188 | 0.949 | 4 216 | -1 262 | 183 | 68 |
| 2.45 | w9 | 350 | 4 946 | 1.123 | 56.3% | -22.6% | 1.161 | 1.086 | 3 205 | 1 741 | 153 | 59 |
| 2.45 | w10 | 281 | 4 973 | 1.168 | 56.2% | -24.2% | 1.030 | 1.346 | 501 | 4 472 | 123 | 49 |
| 2.45 | w11 | 203 | 3 787 | 1.175 | 56.7% | -25.8% | 1.176 | 1.174 | 1 990 | 1 797 | 88 | 44 |
| 2.45 | w14 | 80 | 1 620 | 1.227 | 57.5% | -13.7% | 0.969 | 1.595 | -128 | 1 748 | 34 | 16 |
| 2.45 | w16 | 49 | 2 820 | 1.743 | 63.3% | -9.1% | 1.454 | 2.028 | 858 | 1 962 | 18 | 10 |
| 2.50 | w8 | 407 | 2 105 | 1.046 | 55.0% | -41.9% | 1.166 | 0.936 | 3 641 | -1 537 | 183 | 67 |
| 2.50 | w9 | 347 | 4 745 | 1.119 | 56.2% | -24.3% | 1.137 | 1.101 | 2 730 | 2 014 | 152 | 58 |
| 2.50 | w10 | 278 | 4 966 | 1.167 | 56.1% | -22.3% | 1.008 | 1.379 | 134 | 4 831 | 122 | 48 |
| 2.50 | w11 | 201 | 3 869 | 1.178 | 56.7% | -22.0% | 1.146 | 1.214 | 1 693 | 2 176 | 87 | 43 |
| 2.50 | w14 | 80 | 1 925 | 1.265 | 58.8% | -12.1% | 0.971 | 1.704 | -124 | 2 050 | 33 | 15 |
| 2.50 | w16 | 49 | 3 178 | 1.841 | 65.3% | -12.1% | 1.454 | 2.253 | 888 | 2 290 | 17 | 9 |

## Comparison vs Phase 1A rail 2.35 at same width

This table shows whether transition rails improved over the upper semantic rail `2.35`.

| Width | Rail | ΔPnL vs 2.35 | ΔPF vs 2.35 | ΔMaxDD vs 2.35 | ΔLong PF | ΔShort PF |
|---:|---:|---:|---:|---:|---:|---:|
| w8 | 2.45 | 468 | +0.009 | -1.0% | +0.049 | -0.026 |
| w8 | 2.50 | -381 | -0.008 | -4.5% | +0.027 | -0.038 |
| w9 | 2.45 | 1 068 | +0.022 | -0.6% | +0.056 | -0.012 |
| w9 | 2.50 | 867 | +0.017 | -2.4% | +0.032 | +0.003 |
| w10 | 2.45 | 522 | +0.014 | -0.7% | +0.042 | -0.031 |
| w10 | 2.50 | 514 | +0.013 | 1.2% | +0.020 | +0.002 |
| w11 | 2.45 | -147 | -0.012 | -0.8% | +0.015 | -0.044 |
| w11 | 2.50 | -65 | -0.009 | 3.0% | -0.014 | -0.004 |
| w14 | 2.45 | -243 | -0.044 | -0.4% | +0.035 | -0.209 |
| w14 | 2.50 | 63 | -0.006 | 1.3% | +0.037 | -0.099 |
| w16 | 2.45 | -406 | -0.170 | -0.0% | +0.008 | -0.410 |
| w16 | 2.50 | -48 | -0.072 | -3.0% | +0.008 | -0.185 |

## Readout by width

### w8

```text
2.45:
  PnL +2 954
  PF 1.063
  long PF 1.188
  short PF 0.949

2.50:
  PnL +2 105
  PF 1.046
  long PF 1.166
  short PF 0.936
```

Verdict:

```text
Reject as main branch.
w8 remains long-biased and short side is below 1.
```

### w9

```text
2.45:
  PnL +4 946
  PF 1.123
  long PF 1.161
  short PF 1.086

2.50:
  PnL +4 745
  PF 1.119
  long PF 1.137
  short PF 1.101
```

Verdict:

```text
Strong broad transition candidate.
Both sides remain positive.
2.45 is slightly better raw; 2.50 is slightly more short-balanced.
```

### w10

```text
2.45:
  PnL +4 973
  PF 1.168
  long PF 1.030
  short PF 1.346

2.50:
  PnL +4 966
  PF 1.167
  long PF 1.008
  short PF 1.379
```

Verdict:

```text
Strong PnL, but short-heavy.
Long side survives barely, so this is not the cleanest baseline.
```

### w11

```text
2.45:
  PnL +3 787
  PF 1.175
  long PF 1.176
  short PF 1.174

2.50:
  PnL +3 869
  PF 1.178
  long PF 1.146
  short PF 1.214
```

Verdict:

```text
Best quality transition zone.
2.45 + w11 is the cleanest side-balanced candidate.
2.50 + w11 is slightly more profitable and still healthy.
```

### w14

```text
2.45:
  PF 1.227
  long PF 0.969
  short PF 1.595

2.50:
  PF 1.265
  long PF 0.971
  short PF 1.704
```

Verdict:

```text
Reject as main branch.
Still short-carried; long side below 1.
```

### w16

```text
2.45:
  trades 49
  PF 1.743
  long PF 1.454
  short PF 2.028

2.50:
  trades 49
  PF 1.841
  long PF 1.454
  short PF 2.253
```

Verdict:

```text
Keep as high-selectivity branch.
Do not promote to main baseline until robustness checks.
```

## Decision

Carry forward from Phase 1B:

```text
B1-main:
  2.45 + w11

B2-broad:
  2.45 + w9
  2.50 + w9

B3-profit/short-heavy:
  2.45 + w10
  2.50 + w10

B4-high-selectivity:
  2.50 + w16
```

Do not carry forward as main:

```text
w8:
  short side weak

w14:
  short-carried, long side below 1
```

## Updated overall interpretation after Phase 1B

Phase 1A gave semantic candidates:

```text
2.15 + w11:
  clean main semantic candidate

2.35 + w9:
  broad balanced semantic candidate

2.35 + w11:
  upper semantic quality candidate
```

Phase 1B adds transition candidates:

```text
2.45 + w11:
  clean transition quality candidate

2.45 + w9:
  broad transition candidate

2.50 + w9:
  broad transition boundary candidate

2.50 + w16:
  high-selectivity branch
```

The best practical comparison set is now:

```text
Semantic:
  2.15 + w11
  2.35 + w9
  2.35 + w11

Transition:
  2.45 + w9
  2.45 + w11
  2.50 + w9
  2.50 + w11

High-selectivity:
  2.35 + w16
  2.50 + w16
```

## Recommended next step

Do not add RSI yet if we want a clean architecture of causes.

Next best step:

```text
Phase 2A:
  tune recent_width and width_lookback
  around current_width w9 / w11
  on rails 2.15 / 2.35 / 2.45
```

Why include 2.45 now:

```text
2.45 + w11 is clean and side-balanced.
It deserves to be tested as transition-quality candidate, not dismissed.
```

Suggested Phase 2A compact matrix:

```text
current_width:
  w9
  w11

recent_width:
  r8
  r10
  r12
  r14

width_lookback:
  lb10
  lb20
  lb35

rails:
  2.15
  2.35
  2.45
```

Total:

```text
2 × 4 × 3 × 3 = 72 candidates
```

Separate later:

```text
Phase 2B:
  high-selectivity robustness
  w14/w16
  rails 2.35/2.45/2.50
```

## Chart files

```text
charts/01_phase1b_pnl_by_width.png
charts/02_phase1b_pf_by_width.png
charts/03_phase1b_long_pf_by_width.png
charts/04_phase1b_short_pf_by_width.png
charts/05_phase1b_max_dd_by_width.png
charts/06_pf_comparison_semantic_vs_transition.png
```
