# Findings — EMA200 phase-gated runner exit v1 fee04

Fill after batch run.

## Batch

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04.json
```

## Summary table

| Candidate | Trades | PnL | PF | DD | Runner trades | Runtime exits | RSI runtime | EMA runtime | Runner -> SL | Long PF | Short PF | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| strict_initial_control_fee04 | | | | | | | | | | | | |
| strict_adx40_runner_no_signal_fee04 | | | | | | | | | | | | |
| strict_adx40_runner_only_rsi90_fee04 | | | | | | | | | | | | |
| strict_adx40_runner_only_ema100_200_fee04 | | | | | | | | | | | | |
| strict_adx40_runner_rsi90_plus_ema100_200_fee04 | | | | | | | | | | | | |
| strict_adx45_runner_rsi90_plus_ema100_200_fee04 | | | | | | | | | | | | |

## Checks

```text
runtime exits before runner = ?
exit_layer_breakdown has exit_management.runtime_exit = ?
runtime_exit_breakdown has rsi_signal_exit = ?
runtime_exit_breakdown has ema_cross_loss_exit = ?
```

## Decision

Keep:

```text

```

Reject:

```text

```

Next:

```text

```
