# EMA200 Research Step 0 — setup universe before stop/partial/trailing work

## Why this Step 0 exists

Before adding new execution mechanics like partial take, break-even, lock stop or trailing, we need to compare the runner exit logic across more than the current strict setup.

The current strict branch has good edge, but only around 135 trades in the tested history. The relaxed branch had more trades in earlier phases, so it should be re-tested under the same new phase-gated runner runtime.

This Step 0 answers:

```text
Do RSI90 / RSI88 / EMA100/200 runner exits still work when the setup is relaxed?
Can a more frequent setup produce enough trades while keeping PF and avg trade acceptable?
Is the strict edge too sparse, or is it genuinely better?
```

## Common strategy

```text
symbol: BTCUSDT
timeframe: 5m
sides: long + short
anchor stack: EMA100 / EMA200 / EMA496 close
direction: ema_anchor_stack_trend
trigger: touch_anchor
blockers: no_blockers
risk: no_risk_filter
fees: 0.0004
slippage: 0.0001
```

## Setup profiles

### strict

Current best strict setup.

```text
width:
  min_current_width_atr: 12
  min_recent_width_atr: 14
  width_lookback_bars: 20

untouched:
  lookback: 75
  active_bars: 8

initial exits:
  SL: 6 ATR
  TP: 14 ATR
```

### relaxed

Known relaxed medium setup from earlier research phases. Expected: more trades, lower per-trade quality.

```text
width:
  min_current_width_atr: 9
  min_recent_width_atr: 10
  width_lookback_bars: 20

untouched:
  lookback: 75
  active_bars: 8

initial exits:
  SL: 4 ATR
  TP: 10 ATR
```

### loose_probe

New exploratory setup probe. This is not an accepted production setup. It exists only to test whether the entry universe can be expanded toward 250–400 trades.

```text
width:
  min_current_width_atr: 8
  min_recent_width_atr: 9
  width_lookback_bars: 30

untouched:
  lookback: 50
  active_bars: 12

initial exits:
  SL: 4 ATR
  TP: 10 ATR
```

## Exit modes per setup

Each setup profile runs the same five modes:

```text
initial_control
adx40 runner + RSI90/10
adx40 runner + RSI88/12
adx40 runner + EMA100/200 protective
adx40 runner + RSI90/10 + EMA100/200 protective
```

Runner phase:

```text
adx_di_threshold:
  timeframe: base
  period: 14
  threshold: 40
  require_di_alignment: true

on runner:
  disable initial TP
```

## Candidates

```text
strict_initial_control_fee04
strict_adx40_runner_rsi90_fee04
strict_adx40_runner_rsi88_fee04
strict_adx40_runner_ema100_200_fee04
strict_adx40_runner_rsi90_plus_ema100_200_fee04

relaxed_initial_control_fee04
relaxed_adx40_runner_rsi90_fee04
relaxed_adx40_runner_rsi88_fee04
relaxed_adx40_runner_ema100_200_fee04
relaxed_adx40_runner_rsi90_plus_ema100_200_fee04

loose_probe_initial_control_fee04
loose_probe_adx40_runner_rsi90_fee04
loose_probe_adx40_runner_rsi88_fee04
loose_probe_adx40_runner_ema100_200_fee04
loose_probe_adx40_runner_rsi90_plus_ema100_200_fee04
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_step0_setup_universe_runner_exit_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_step0_setup_universe_runner_exit_fee04.json
```

## What to inspect

For every setup profile and exit mode:

```text
total trades
closed/open trades
PnL
PF
win rate
avg win
avg loss
avg trade
average hold
median hold
long PF
short PF
runner trades
runner PnL
runner exit mix: RSI / EMA / SL
non-runner TP count
non-runner SL count
PnL by bucket
```

## Step 0 acceptance

A more frequent setup is interesting only if it satisfies at least:

```text
trades: materially higher than strict
PF: > 1.25
avg trade: positive after fees
long and short: neither side completely dead
runner cohort: still positive
drawdown: not catastrophically worse than strict
```

A setup is rejected if it only increases trade count by adding low-quality non-runner SLs.

## Current expected interpretation

```text
strict:
  likely best edge quality, sparse trades

relaxed:
  likely more trades, may reveal whether edge survives with larger sample

loose_probe:
  exploratory; useful only if trade count rises without destroying PF
```
