# Phase 8 — Dynamic Exit Research

## Fix note

These configs are in **loader format**, not report/wire format.

Do not include report-only/null superset fields in config exits.

Correct ATR stop-loss / take-profit shape:

```json
{
  "instance_id": "atr_sl",
  "component_id": "atr_stop_loss",
  "distance": {
    "timeframe": "base",
    "period": 14,
    "multiplier": 4.0
  }
}
```

Correct RSI signal-exit shape:

```json
{
  "instance_id": "rsi_1h_70_30",
  "component_id": "rsi_signal_exit",
  "rsi": {
    "timeframe": "1h",
    "period": 14
  },
  "long_exit_above": 70.0,
  "short_exit_below": 30.0
}
```

## Research purpose

Phase 8 starts testing dynamic exits instead of fixed ATR TP.

Phase 8 order:

1. 1h RSI overheat exits.
2. EMA trailing / EMA loss-of-momentum exits.
3. Break-even stop after signal exits are understood.

## Baselines

### Relaxed

```text
EMA stack: 100 / 200 / 496
width: current 9 ATR, recent 10 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 4 ATR
Safety TP: 40 ATR
```

### Strict

```text
EMA stack: 100 / 200 / 496
width: current 12 ATR, recent 14 ATR, lookback 20
untouched anchor: lookback 75, active bars 8
SL: 6 ATR
Safety TP: 40 ATR
```

The safety TP is not the intended profit-taking mechanism. It is only a far cap.

## Phase 8A — 1h RSI overheat exits

Batch:

```text
research/experiments/configs/ema_pullback/width_sweeps/width_phase8a_ema200_1h_rsi_overheat_exit_sweep.json
```

Candidates:

```text
relaxed control, no signal exit
strict control, no signal exit

relaxed 1h RSI 65/35
relaxed 1h RSI 70/30
relaxed 1h RSI 75/25
relaxed 1h RSI 80/20

strict 1h RSI 65/35
strict 1h RSI 70/30
strict 1h RSI 75/25
strict 1h RSI 80/20
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase8a_ema200_1h_rsi_overheat_exit_sweep.json
```

## Optional Phase 8A.2 — confirm_bars=2

Batch:

```text
research/experiments/configs/ema_pullback/width_sweeps/width_phase8a2_ema200_1h_rsi_overheat_confirm2_sweep.json
```

Run only if the loader accepts `confirm_bars` for `rsi_signal_exit`.

## What to inspect

Use `*.summary.json`.

Primary questions:

```text
Does rsi_signal_exit become a meaningful exit reason?
Does it reduce high_mfe_low_capture?
Does it reduce avg/median giveback_pct?
Does it improve capture_ratio?
Does it preserve p75/p90 MFE?
Does 65/35 exit too early?
Does 80/20 exit too late?
Is 70/30 or 75/25 the useful middle?
```

## Next after Phase 8A

Prepare Phase 8B only after reviewing 8A:

```text
EMA20 / EMA30 / EMA50 trailing or loss-of-momentum exits
possible EMA cross exits
```

Break-even comes after that:

```text
activation: 0.75 / 1.0 / 1.5 / 2.0 ATR
offset: 0 / fees / 0.25 ATR
```
