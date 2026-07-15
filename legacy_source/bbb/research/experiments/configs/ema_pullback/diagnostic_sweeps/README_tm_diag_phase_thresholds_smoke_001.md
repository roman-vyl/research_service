# tm_diag_phase_thresholds_smoke_001

Small diagnostic-only smoke batch for trade-management phase diagnostics.

## Candidates

Base strategy families:

1. `relaxed_w9_r10_sl4`
   - width current/recent: 9 / 10 ATR
   - untouched lookback: 75
   - active bars: 8
   - ATR SL: 4
   - safety TP: 40 ATR

2. `strict_w12_r14_sl6`
   - width current/recent: 12 / 14 ATR
   - untouched lookback: 75
   - active bars: 8
   - ATR SL: 6
   - safety TP: 40 ATR

Diagnostics ladders:

- `atr3_6_9`: proven 3 ATR, protected 6 ATR, runner 9 ATR
- `atr4_8_12`: proven 4 ATR, protected 8 ATR, runner 12 ATR
- `atr5_10_15`: proven 5 ATR, protected 10 ATR, runner 15 ATR

Also includes baseline/no-exit-management candidates for each base family.

## Run

From repo root:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/diagnostic_sweeps/tm_diag_phase_thresholds_smoke_001.json
```

## What to inspect

For each diagnostic candidate:

- `metrics.trade_management_summary.by_phase_reached`
- `runner_capture_summary`
- `protected_trade_summary`
- `trade_management_events` count in full report
- compact `.summary.json` keeps `metrics.trade_management_summary` and strips heavy events/trades

Expected behavior:

- baseline and diagnostic variants with the same base strategy should have identical trade count / PnL / PF / exit reasons.
- diagnostic variants only change report diagnostics, not execution.
