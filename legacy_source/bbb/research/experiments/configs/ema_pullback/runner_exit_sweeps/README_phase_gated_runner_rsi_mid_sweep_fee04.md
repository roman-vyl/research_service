# EMA200 phase-gated runner RSI midpoint sweep fee04

Purpose: test thresholds between already-run RSI85/15 and RSI90/10 under the same ADX40 runner setup.

## Scope

Keep the same proven baseline:

```text
BTCUSDT 5m
EMA stack 100/200/496
width setup: current 12 ATR, recent 14 ATR, lookback 20
untouched lookback 75 / active 8
initial SL 6 ATR
initial TP 14 ATR
ADX/DI 40 -> runner
runner disables initial TP
fees 0.0004
```

## Candidates

RSI-only:

```text
strict_adx40_runner_only_rsi86_14_fee04
strict_adx40_runner_only_rsi87_13_fee04
strict_adx40_runner_only_rsi88_12_fee04
strict_adx40_runner_only_rsi89_11_fee04
```

RSI + EMA100/200 protective:

```text
strict_adx40_runner_rsi86_14_plus_ema100_200_fee04
strict_adx40_runner_rsi87_13_plus_ema100_200_fee04
strict_adx40_runner_rsi88_12_plus_ema100_200_fee04
strict_adx40_runner_rsi89_11_plus_ema100_200_fee04
```

## Reference points from previous run

```text
RSI85-only:
  PnL +13 544
  PF 1.455
  runner mix: 19 RSI / 0 EMA / 8 SL

RSI90-only:
  PnL +16 789
  PF 1.558
  runner mix: 15 RSI / 0 EMA / 12 SL

RSI90+EMA100/200:
  PnL +13 656
  PF 1.511
  runner mix: 7 RSI / 17 EMA / 3 SL
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_rsi_mid_sweep_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_rsi_mid_sweep_fee04.json
```

## What to inspect

```text
total PnL / PF / DD
long PF / short PF
runner exit mix: RSI / EMA / SL
runner capture median
runner giveback median
whether threshold 88/12 or 89/11 gives better compromise than 85/15 and 90/10
```

Expected useful outcome:

```text
RSI88/12 or RSI89/11 may reduce runner->SL versus RSI90
without cutting as much tail PnL as RSI85.
```
