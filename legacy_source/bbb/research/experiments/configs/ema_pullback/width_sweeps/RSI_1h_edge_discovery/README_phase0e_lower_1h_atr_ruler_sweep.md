# RSI 1h Edge Discovery — Phase 0E Lower 1h ATR Ruler Sweep

## Why this phase exists

Phase 0C/0D showed that wider 1h ATR rails can produce more PnL:

```text
1hATR 3–4
```

But this creates a semantic problem.

On a 5m EMA200 pullback chart, `3–4 × 1h ATR` can be so wide that:

```text
SL/TP is larger than the local EMA-stack structure
SL can go far beyond the EMA200 pullback area
sometimes even below much slower anchors such as EMA1000-like structure
the test starts measuring wide continuation holding instead of EMA200 pullback behavior
```

So this phase deliberately searches lower values again.

## Goal

Find a lower symmetric 1h ATR ruler that is:

```text
stable
both-side interpretable
not pure fee churn
not an oversized continuation proxy
still close enough to EMA200 pullback structure
```

## Batch

```text
batches/ema200_rsi_1h_edge_phase0e_lower_1h_atr_ruler_sweep_fee04.json
```

## Matrix

Profiles:

```text
relaxed_known:
  width w9/r10/lb20
  untouched75/active8

strict_known:
  width w12/r14/lb20
  untouched75/active8
```

Rails:

```text
1h ATR symmetric SL/TP
0.75 to 2.50
step 0.05
```

Total:

```text
2 profiles × 36 rails = 72 candidates
```

## Important

`2.50` is not the target. It is only an upper comparator.

The target zone is expected to be somewhere below the wide-continuation region:

```text
roughly 1.50–2.50
```

but the sweep includes `0.75–1.45` to verify where noise/fees dominate.

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0e_lower_1h_atr_ruler_sweep_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0e_lower_1h_atr_ruler_sweep_fee04.json
```

## What to compare

Do not select by PnL only.

Compare:

```text
PF
PnL
maxDD
win rate
long PF
short PF
long PnL
short PnL
trade count
fees paid
stop_loss_after_bad_context
stop_loss_after_low_mfe
high_mfe_high_capture_count
high_mfe_low_capture_count
```

## Selection rule

Preferred lower ruler:

```text
PF clearly above 1
both long and short PF above or near 1
drawdown does not explode
result is not only short-carried
trade count remains stable
rail still describes pullback scale, not broad continuation holding
```

Reject:

```text
fee churn at low values
one-side-only result
wide-continuation behavior
large PnL with weak long side
maxDD expansion that suggests the SL is too wide
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
HTF context
asymmetric rails
```
