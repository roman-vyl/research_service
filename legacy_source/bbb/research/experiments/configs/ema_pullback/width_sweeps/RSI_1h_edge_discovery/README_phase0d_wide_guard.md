# RSI 1h Edge Discovery — Phase 0D Wide Guard

## Why Phase 0D exists

Phase 0C did not close the boundary.

Best observed Phase 0C result:

```text
relaxed_known + 1hATR SL3 / TP3
PnL +10 727
PF 1.178
long PF 1.134
short PF 1.223
```

Strict also improved at `3.0`:

```text
strict_known + 1hATR SL3 / TP3
PnL +5 595
PF 1.310
long PF 1.198
short PF 1.473
```

This means the current best value is still the upper boundary.

## Phase 0D purpose

Check whether `3.0` is a local peak or whether wider 1h ATR symmetric rails continue improving.

## Batch

```text
batches/ema200_rsi_1h_edge_phase0d_1h_atr_wide_guard_sweep_fee04.json
```

## Matrix

Profiles:

```text
relaxed_known:
  w9/r10/lb20
  untouched75/active8

strict_known:
  w12/r14/lb20
  untouched75/active8
```

Rails:

```text
1hATR symmetric:
  3.00
  3.25
  3.50
  3.75
  4.00
```

Total:

```text
2 profiles × 5 rails = 10 candidates
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0d_1h_atr_wide_guard_sweep_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0d_1h_atr_wide_guard_sweep_fee04.json
```

## Interpretation

If performance peaks around `3.0–3.25` and then falls:

```text
Use 1hATR 3.0/3.0 as Phase 1 ruler.
```

If performance keeps improving through `4.0`:

```text
Stop treating this as neutral ruler calibration.
This is a wide continuation rail.
Then explicitly decide whether Phase 1 should search width under wide continuation logic.
```

## Still excluded

```text
RSI blocker
RSI gate
ADX runner
runtime exits
BE / lock
partial TP
trailing
asymmetric rails
```
