# RSI 1h Edge Discovery — Phase 0B 1h ATR Fine Sweep

This package extends the corrected Phase 0.

Phase 0 found the best candidate at the upper boundary:

```text
relaxed_known + 1hATR SL2 / TP2
```

So Phase 0B checks whether the real symmetric 1h ATR ruler is slightly below or above 2.0.

## Batch

```text
batches/ema200_rsi_1h_edge_phase0b_1h_atr_symmetric_fine_sweep_fee04.json
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
1h ATR symmetric SL/TP
from 1.50 to 2.50
step 0.05
```

Total:

```text
2 profiles × 21 multipliers = 42 candidates
```

## Important

Still no active RSI filter.

No:

```text
RSI blocker
RSI gate
ADX runner
partial TP
BE / lock
trailing
asymmetric rails
```

Phase 0B only refines the 1h ATR symmetric ruler.

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0b_1h_atr_symmetric_fine_sweep_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0b_1h_atr_symmetric_fine_sweep_fee04.json
```

## What to select

Primary selection should not be by PnL alone.

Compare:

```text
PnL
PF
MaxDD
win rate
avg trade if available
long PF
short PF
long/short PnL
trade count
fees
stop_loss_after_bad_context
```

Good candidate:

```text
PF improves over 1hATR 2/2
both long and short PF remain above or close to 1
drawdown does not explode
trade count remains similar
```

Bad candidate:

```text
only one side carries result
PF gain comes with much higher DD
trade count collapses
larger multiplier starts acting like runner proxy
```

## Expected use

After Phase 0B, pick:

```text
primary 1h ATR symmetric ruler
optional secondary sensitivity ruler
```

Then run Phase 1 current-width sweep.
