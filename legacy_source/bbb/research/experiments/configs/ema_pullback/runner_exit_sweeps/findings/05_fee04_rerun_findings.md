# Fee04 focused rerun findings

Batch family:

```text
EMA200 runner RSI5m focused rerun
fees = 0.0004 one-way
```

Uploaded full reports parsed: **11**.

Missing for complete 14-run batch:

```text
relaxed_medium_sl4_tp10_adx40_runner_disable_tp_rsi5m_p14_90_10_fee04
relaxed_medium_sl4_tp10_adx45_runner_disable_tp_rsi5m_p14_85_15_fee04
relaxed_medium_sl4_tp10_adx45_runner_disable_tp_rsi5m_p14_90_10_fee04
```

## Summary table

| Variant | Trades | PnL | PF | WR | DD | Long PF | Short PF | Runner trades | Runner PnL | Runner PF | RSI pre/after runner |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| strict_continuation_sl6_tp14_initial_control | 138 | 2 639 | 1.357 | 40.6% | -0.112 | 1.223 | 1.585 | 0 | 0 |  | 0/0 |
| strict_continuation_sl6_tp14_rsi5m_p14_85_15_control | 140 | 674 | 1.108 | 43.6% | -0.124 | 1.033 | 1.241 | 0 | 0 |  | 30/0 |
| strict_continuation_sl6_tp14_rsi5m_p14_90_10_control | 140 | 1 522 | 1.220 | 40.7% | -0.112 | 1.117 | 1.395 | 0 | 0 |  | 13/0 |
| strict_continuation_sl6_tp14_adx40_runner_disable_tp_rsi5m_p14_85_15 | 139 | 8 887 | 1.328 | 43.9% | -0.363 | 1.292 | 1.388 | 14 | 7 354 | 3.931 | 28/10 |
| strict_continuation_sl6_tp14_adx40_runner_disable_tp_rsi5m_p14_90_10 | 137 | 13 685 | 1.452 | 37.2% | -0.333 | 1.244 | 1.773 | 23 | 14 908 | 3.843 | 11/12 |
| strict_continuation_sl6_tp14_adx45_runner_disable_tp_rsi5m_p14_85_15 | 140 | 6 603 | 1.244 | 44.3% | -0.431 | 1.200 | 1.317 | 5 | 162 | 1.077 | 30/3 |
| strict_continuation_sl6_tp14_adx45_runner_disable_tp_rsi5m_p14_90_10 | 140 | 11 866 | 1.400 | 40.0% | -0.359 | 1.188 | 1.724 | 11 | 7 831 | 3.483 | 11/7 |
| relaxed_medium_sl4_tp10_initial_control | 357 | 2 286 | 1.122 | 34.7% | -0.199 | 1.248 | 0.981 | 0 | 0 |  | 0/0 |
| relaxed_medium_sl4_tp10_rsi5m_p14_85_15_control | 362 | -277 | 0.983 | 38.1% | -0.145 | 1.113 | 0.834 | 0 | 0 |  | 52/0 |
| relaxed_medium_sl4_tp10_rsi5m_p14_90_10_control | 359 | 1 090 | 1.061 | 35.9% | -0.183 | 1.182 | 0.923 | 0 | 0 |  | 20/0 |
| relaxed_medium_sl4_tp10_adx40_runner_disable_tp_rsi5m_p14_85_15 | 361 | 3 358 | 1.044 | 37.4% | -0.533 | 1.136 | 0.928 | 22 | 13 065 | 4.984 | 47/13 |

## Runner cohort table

| Variant | Runner trades | Runner PnL | Runner PF | WR | Avg MFE | P90 MFE | Median capture | Avg giveback | Exit mix | Runner side PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| strict_continuation_sl6_tp14_adx40_runner_disable_tp_rsi5m_p14_85_15 | 14 | 7 354 | 3.931 | 71.4% | 2.2% | 3.8% | 0.871 | 1.1% | signal:rsi5m_p14_85_15: 10, stop_loss:sl_6p0atr: 4 | long: 5 106, short: 2 248 |
| strict_continuation_sl6_tp14_adx40_runner_disable_tp_rsi5m_p14_90_10 | 23 | 14 908 | 3.843 | 52.2% | 4.6% | 7.0% | 0.095 | 2.6% | stop_loss:sl_6p0atr: 11, signal:rsi5m_p14_90_10: 12 | short: 8 752, long: 6 155 |
| strict_continuation_sl6_tp14_adx45_runner_disable_tp_rsi5m_p14_85_15 | 5 | 162 | 1.077 | 60.0% | 2.5% | 3.8% | 0.475 | 2.2% | signal:rsi5m_p14_85_15: 3, stop_loss:sl_6p0atr: 2 | long: 700, short: -539 |
| strict_continuation_sl6_tp14_adx45_runner_disable_tp_rsi5m_p14_90_10 | 11 | 7 831 | 3.483 | 63.6% | 5.7% | 7.2% | 0.390 | 3.3% | signal:rsi5m_p14_90_10: 7, stop_loss:sl_6p0atr: 4 | long: 1 935, short: 5 896 |
| relaxed_medium_sl4_tp10_adx40_runner_disable_tp_rsi5m_p14_85_15 | 22 | 13 065 | 4.984 | 59.1% | 1.9% | 3.4% | 0.600 | 1.2% | stop_loss:sl_4p0atr: 9, signal:rsi5m_p14_85_15: 13 | short: 2 925, long: 10 139 |

## Main conclusions

### 1. `fees=0.0004` confirms the signal

The ranking did not collapse after moving from the old stress fee model to a more realistic conservative mixed fee model.

The best uploaded candidate is still:

```text
strict_continuation_sl6_tp14
ADX40 -> runner
disable initial TP at runner
RSI5m period 14, 90/10 signal exit
```

It produced:

```text
PnL: 13 685
PF: 1.452
WR: 37.2%
DD: -0.333
Long PF: 1.244
Short PF: 1.773
Runner trades: 23
Runner PnL: 14 908
Runner PF: 3.843
```

### 2. RSI-only remains weak

RSI control variants do not prove an edge by themselves.

Strict controls:

```text
initial: PnL 2 639, PF 1.357
RSI85 control: PnL 674, PF 1.108
RSI90 control: PnL 1 522, PF 1.220
```

Relaxed controls:

```text
initial: PnL 2 286, PF 1.122
RSI85 control: PnL -277, PF 0.983
RSI90 control: PnL 1 090, PF 1.061
```

So RSI is not the source of the strategy by itself. The money appears when RSI is used after a runner selection context.

### 3. ADX40 is better than ADX45 for strict runner switching

Strict ADX40 / RSI90:

```text
PnL 13 685
PF 1.452
runner trades 23
runner PnL 14 908
```

Strict ADX45 / RSI90:

```text
PnL 11 866
PF 1.400
runner trades 11
runner PnL 7 831
```

ADX45 is cleaner/stricter but seems too late or too selective for the runner switch.

### 4. RSI90 is better for money, RSI85 is better for capture/winrate

Strict ADX40 / RSI85:

```text
PnL 8 887
PF 1.328
WR 43.9%
runner median capture 0.871
avg giveback 1.05%
```

Strict ADX40 / RSI90:

```text
PnL 13 685
PF 1.452
WR 37.2%
runner median capture 0.095
avg giveback 2.56%
```

RSI90 captures larger tails but gives back more. RSI85 captures more tightly, but cuts too much of the large move.

### 5. Relaxed ADX40 RSI85 is not good enough

Uploaded relaxed runner candidate:

```text
relaxed ADX40 RSI85
PnL 3 358
PF 1.044
DD -0.533
Long PF 1.136
Short PF 0.928
```

Runner cohort is good:

```text
runner trades 22
runner PnL 13 065
runner PF 4.984
```

But the non-runner / initial-risk mass is too bad:

```text
initial-risk PnL -9 707
initial-risk PF 0.868
```

So relaxed still needs either better entry filtering or only survives if RSI90 runner tail is huge. The missing relaxed RSI90 runner reports are needed before final relaxed conclusion.

## Working decision

### Keep / continue

```text
strict ADX40 RSI90
strict ADX45 RSI90
strict ADX40 RSI85 as lower-giveback comparison
```

### Deprioritize

```text
RSI-only controls
strict ADX45 RSI85
relaxed ADX40 RSI85
```

### Need missing reports

```text
relaxed ADX40 RSI90 fee04
relaxed ADX45 RSI85 fee04
relaxed ADX45 RSI90 fee04
```

## Next research step

Before expanding EMA-cross exits, finish the missing relaxed RSI90 runner reports and then compare:

```text
strict ADX40 RSI90
strict ADX45 RSI90
relaxed ADX40 RSI90
relaxed ADX45 RSI90
```

If relaxed ADX40 RSI90 remains very profitable under fee04 but has poor initial-risk mass, then the next design problem is not RSI threshold tuning. It is phase-gated exit semantics and possibly gating/repairing relaxed entries.
