# EMA200 Runner RSI5m — focused fee04 rerun

This package is a focused rerun of the strongest Phase 1 runner-exit candidates with:

```text
fees = 0.0004
```

Interpretation:

```text
0.0006 = stress / old conservative mode
0.0004 = conservative mixed Bybit maker/taker research mode
0.0003 = optimistic maker-biased mode, intentionally not used here
```

## Why this batch exists

The previous RSI5m Phase 1 run was performed with `fees=0.0006`, which is too harsh for normal Bybit futures/perps research if entries are at least partially maker/limit and not every fill is pure taker.

We do **not** switch to `0.0003` yet because that would be too optimistic. This rerun uses `0.0004` as a safer middle ground.

## Scope

This is not a full 32-run sweep. It is a focused confirmation batch:

- initial controls
- RSI85/15 and RSI90/10 controls without runner
- strict/relaxed × ADX40/45 × RSI85/90 runner variants

## Files

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/
  batches/
    ema200_runner_rsi5m_fee04_focused.json

  candidates/fee04_focused/
    14 candidate JSON configs
```

## Run

From repository root:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_runner_rsi5m_fee04_focused.json
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_runner_rsi5m_fee04_focused.json
```

## What to compare

Primary comparison:

```text
strict initial fee04
strict RSI85/90 control fee04
strict ADX40/45 -> runner + disable initial TP + RSI85/90 fee04

relaxed initial fee04
relaxed RSI85/90 control fee04
relaxed ADX40/45 -> runner + disable initial TP + RSI85/90 fee04
```

Key metrics:

```text
net PnL
gross PnL
fees paid
PF
win rate
max drawdown
long PF / short PF
exit_reason_mix
trade_management_summary.by_phase_reached.runner
runner_capture_summary
take_management_breakdown.take_profile_switch
```

## Expected hypotheses

### H1

ADX/DI should be interpreted as a runner selector, not as a hard BE trigger.

### H2

RSI5m only becomes useful when it is late/extreme enough, especially `90/10`.

### H3

`ADX40` may be better than `ADX45` for runner switching, because `ADX45` can trigger too late.

### H4

`strict ADX40 RSI90` is likely the best quality/PF candidate.

### H5

`relaxed ADX40 RSI90` may remain the best raw money candidate, but must be checked for fee sensitivity, drawdown, and outlier concentration.

## After run

Write results into:

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/findings/05_fee04_rerun_findings.md
```
