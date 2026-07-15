# EMA200 phase-gated runner exit research v1

Purpose: test the new `exit_management.runtime_exit` architecture on real EMA200 runner candidates.

This package intentionally uses the old RSI/EMA primitives in the new runtime role:

```text
rsi_signal_exit       -> exit_management.runtime_exit, exit_kind: take_profit
ema_cross_loss_exit   -> exit_management.runtime_exit, exit_kind: protective_exit
```

No `runner_rsi_exit`, no `phase_gated_ema_cross_exit`, no always-on RSI/EMA signal exits.

## Baseline strategy

```text
BTCUSDT 5m
EMA stack: 100 / 200 / 496
setups:
  anchor_stack_width_setup: current width 12 ATR, recent max width 14 ATR, lookback 20
  untouched_anchor_setup: lookback 75, active_bars 8
trigger: touch_anchor
sides: long + short
fees: 0.0004
slippage: 0.0001
initial SL: 6 ATR
initial TP: 14 ATR
```

## Candidate matrix

Controls:

```text
strict_initial_control_fee04
strict_adx40_runner_no_signal_fee04
strict_adx45_runner_no_signal_fee04
```

ADX40 runtime exits:

```text
strict_adx40_runner_only_rsi90_fee04
strict_adx40_runner_only_rsi85_fee04
strict_adx40_runner_only_ema100_200_fee04
strict_adx40_runner_only_ema50_200_fee04
strict_adx40_runner_rsi90_plus_ema100_200_fee04
strict_adx40_runner_rsi85_plus_ema100_200_fee04
```

ADX45 runtime exits:

```text
strict_adx45_runner_only_rsi90_fee04
strict_adx45_runner_only_rsi85_fee04
strict_adx45_runner_only_ema100_200_fee04
strict_adx45_runner_only_ema50_200_fee04
strict_adx45_runner_rsi90_plus_ema100_200_fee04
strict_adx45_runner_rsi85_plus_ema100_200_fee04
```

## Commands

Copy files into repo root preserving paths.

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04.json
```

## What to inspect

For every candidate:

```text
total PnL / PF / Sharpe / DD
long PF and short PF
trade count
runner trade count
exit_layer_breakdown
runtime_exit_breakdown.by_component_id
runtime_exit_breakdown.by_rule_id
runner -> runtime RSI count
runner -> runtime EMA count
runner -> initial SL count
runner capture / giveback
pre-runner runtime exits = 0
```

## Expected interpretation

Good combined candidate:

```text
keeps total PnL close to RSI90-only
reduces runner -> initial SL compared to RSI90-only
keeps EMA protective exits high
keeps both long and short PF > 1
improves runner capture/giveback profile
```

Bad candidate:

```text
many runner trades still die at initial SL
runtime exits before runner > 0
PF improves only by reducing trade count too much
short side breaks
EMA exits cut too early and destroy tail PnL
```
