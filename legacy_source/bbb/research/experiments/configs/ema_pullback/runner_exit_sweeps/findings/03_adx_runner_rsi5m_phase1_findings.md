# ADX runner + RSI 5m Phase 1 findings

## Batch

Original batch result:

```text
research/experiments/specs/batches/ema200_runner_rsi5m_phase1.json
```

Run result file:

```text
research/results/batches/ema200_runner_rsi5m_phase1.json
```

Important current limitation:

```text
RSI signal exit is still an exit_policy signal.
It is not yet phase-gated to runner only.
Some RSI exits can occur before runner.
```

## Tested idea

```text
ADX/DI threshold -> runner
runner -> disable initial TP
RSI 5m period 14 -> overheat/exhaustion signal exit
```

Tested thresholds:

```text
RSI 70/30
RSI 75/25
RSI 80/20
RSI 85/15
RSI 90/10
```

## Main result

RSI 5m alone is not enough. The edge appears in the combination:

```text
ADX/DI -> runner
+ disable initial TP
+ RSI 5m 90/10
```

RSI-only controls were worse than initial fixed TP baselines.

## Top variants at current fee 0.0006

| Candidate | Net PnL | PF | Win rate | Max DD | Long PF | Short PF | Runner trades | Runner PnL | Runner PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| relaxed ADX40 RSI90 | 13,484 | 1.159 | 33.9% | -0.486 | 1.179 | 1.134 | 25 | 26,848 | 6.048 |
| strict ADX40 RSI90 | 11,225 | 1.353 | 36.5% | -0.359 | 1.155 | 1.660 | 23 | 14,549 | 3.680 |
| strict ADX45 RSI90 | 9,370 | 1.301 | 39.3% | -0.392 | 1.098 | 1.611 | 11 | 7,642 | 3.362 |
| strict ADX40 RSI85 | 6,397 | 1.225 | 43.2% | -0.424 | 1.192 | 1.279 | 14 | 7,121 | 3.759 |
| relaxed ADX45 RSI90 | 6,140 | 1.072 | 34.9% | -0.565 | 1.013 | 1.147 | 12 | 16,451 | 8.030 |

## Strict ADX40 RSI90 detail

```text
Total trades: 137
Net PnL: 11,225
PF: 1.353
Win rate: 36.5%
Max DD: -0.359

Long PF: 1.155
Short PF: 1.660
```

Exit breakdown:

```text
stop_loss: 85 trades, pnl -31,745
initial TP: 29 trades, pnl +19,326
RSI signal: 23 trades, pnl +23,644
```

Phase breakdown:

```text
initial_risk:
  trades: 114
  pnl: -3,325
  PF: 0.874

runner:
  trades: 23
  pnl: +14,549
  PF: 3.680
  exit mix: 12 RSI exits, 11 stop losses
```

Interpretation:

```text
The ordinary initial-risk population is weak under 0.0006 fees.
The runner subset is strong.
This supports using ADX/DI as runner selector.
```

## Strict ADX45 RSI90 detail

```text
Total trades: 140
Net PnL: 9,370
PF: 1.301
Win rate: 39.3%
Max DD: -0.392

Runner trades: 11
Runner PnL: +7,642
Runner PF: 3.362
```

Interpretation:

```text
ADX45 is cleaner/rarer but likely too late for max runner capture.
ADX40 is currently preferred for runner activation.
```

## Relaxed ADX40 RSI90 detail

```text
Total trades: 354
Net PnL: 13,484
PF: 1.159
Win rate: 33.9%
Max DD: -0.486

Long PF: 1.179
Short PF: 1.134
```

Phase breakdown:

```text
initial_risk:
  trades: 329
  pnl: -13,364
  PF: 0.832

runner:
  trades: 25
  pnl: +26,848
  PF: 6.048
```

Interpretation:

```text
Relaxed is not broadly clean.
It becomes rich because a small runner cohort is extremely profitable.
This needs outlier/year split before acceptance.
```

## RSI threshold interpretation

RSI 70/30, 75/25, and 80/20 were generally too early.

```text
They increased win rate in some cases but cut off runner tails.
```

RSI 85/15 is more stable for strict:

```text
strict ADX40 RSI85:
  PF 1.225
  win rate 43.2%
  runner capture ratio much better than RSI90
```

RSI 90/10 is the best money/PF signal so far:

```text
It is rare enough to let runners breathe.
It captures larger tails.
It has lower win rate than 85/15 but higher total expectancy.
```

## Capture warning

Strict ADX40 RSI90 runner metrics:

```text
avg MFE: 4.64%
p90 MFE: 7.02%
avg capture_ratio: 0.205
median capture_ratio: 0.095
```

Relaxed ADX40 RSI90 runner metrics:

```text
avg MFE: 4.41%
p90 MFE: 7.56%
avg capture_ratio: 0.124
median capture_ratio: -0.237
```

This means RSI90 finds money, but still gives back a lot. Future EMA loss-of-momentum exits or lock-profit rules may improve capture.

## Current conclusion

Promising path:

```text
ADX40 -> runner
runner -> disable initial TP
RSI 5m 90/10 as late exit
```

Best quality candidate:

```text
strict ADX40 RSI90
```

Best money candidate:

```text
relaxed ADX40 RSI90
```

Do not broaden the strategy grid until fee-mode rerun and outlier/year diagnostics are reviewed.
