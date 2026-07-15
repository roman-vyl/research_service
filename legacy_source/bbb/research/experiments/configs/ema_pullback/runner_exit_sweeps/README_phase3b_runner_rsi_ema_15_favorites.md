# Phase 3B — runner RSI/EMA exits on 15 Phase 3A favorites

## Purpose

This package tests Trade Management System behavior after Phase 3A initial SL/TP discovery.

We keep all 15 Phase 3A favorite branches and compare:

```text
initial-only baseline
vs
ADX/DI runner activation -> disable initial TP -> runtime exit
```

## ADX used for runner activation

The old runner activation used:

```text
timeframe: base
base timeframe: 5m
indicator: ADX/DI
period: 14
thresholds: 40 and 45
require_di_alignment: true
```

So this package uses both:

```text
ADX(14) >= 40 with DI aligned to trade side
ADX(14) >= 45 with DI aligned to trade side
```

## Important exclusions

```text
No break-even.
No protected phase.
No stop management.
No partial TP.
No trailing.
No new blockers.
```

Phase jumps directly:

```text
initial -> runner
```

At runner activation:

```text
initial TP is disabled
original initial SL remains active
runtime exits become active
```

## Runtime exit profiles

```text
runner_no_signal
runner_rsi85_15
runner_rsi90_10
runner_ema100_200
runner_rsi85_15_plus_ema100_200
runner_rsi90_10_plus_ema100_200
```

RSI exit:

```text
component: rsi_signal_exit
timeframe: base / 5m
period: 14
85/15 or 90/10
exit_kind: take_profit
```

EMA exit:

```text
component: ema_cross_loss_exit
timeframe: base / 5m
fast EMA: 100 close
slow EMA: 200 close
confirm_bars: 1
exit_kind: protective_exit
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase3b_runner_rsi_ema_15_favorites_fee04.json
```

## Candidates

```text
candidates/phase3b_runner_rsi_ema_15_favorites/
```

## Total candidates

```text
195
```

Breakdown:

```text
15 initial controls
15 favorites * 2 ADX thresholds * 6 runner exit profiles = 180 managed candidates
total = 195
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_rsi_1h_edge_phase3b_runner_rsi_ema_15_favorites_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_rsi_1h_edge_phase3b_runner_rsi_ema_15_favorites_fee04.json
```

## Analysis target

Do not choose by raw PnL only.

For each favorite, compare managed variants against its own initial control:

```text
PF delta
PnL delta
WR delta
MaxDD delta
long PF / short PF / gap delta
high_mfe_high_capture
high_mfe_low_capture
signal_exit_winners
signal_exit_giveback_failures
stop_loss_after_low_mfe
stop_loss_after_bad_context
```
