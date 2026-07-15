# RSI 1h Edge Discovery — Phase 2C Width ATR Timeframe Sensitivity

## Purpose

Phase 2B closed the first width-core discovery pass.

Final Phase 2B core:

```text
main stability baseline:
  2.15 + w11/r12/lb20
  width_atr_timeframe = base

sharp comparator:
  2.15 + w11/r12/lb10
  width_atr_timeframe = base

upper semantic comparator:
  2.35 + w11/r12/lb20

transition comparator:
  2.45 + w11/r12/lb20
```

But this leaves one unresolved measurement question:

```text
Should anchor-stack width be normalized by base/5m ATR,
or by 1h ATR?
```

Phase 2C tests exactly that.

## What changes

Only this changes:

```text
anchor_stack_width_setup.atr_timeframe
```

From:

```text
base
```

To:

```text
1h
```

## What does NOT change

The strategy remains a 5m EMA200 pullback strategy.

```text
base timeframe:
  5m

EMA stack:
  base timeframe, close source, fast 100 / anchor 200 / slow 496

SL/TP:
  symmetric 1h ATR rails

trigger:
  touch_anchor

untouched setup:
  lookback 75
  active_bars 8
```

Still excluded:

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

## Why this matters before RSI

We should not add RSI 1h as an active filter before checking whether the existing width measurement is on the right volatility ruler.

If 1h ATR width normalization makes the width gate smoother, more stable, or more side-balanced, then RSI tests should be run on that width scale.

If 1h ATR width normalization weakens or blurs the edge, then base ATR width remains the correct entry geometry ruler.

## Important scale warning

Do not copy old thresholds directly.

Old Phase 2B used:

```text
base ATR width:
  w11/r12
```

That means:

```text
stack_width / ATR_5m
```

Phase 2C 1h-width candidates use:

```text
stack_width / ATR_1h
```

Since 1h ATR is normally larger than 5m ATR, the same market structure will produce lower numeric width values on the 1h ATR scale.

So Phase 2C is a new scale discovery, not a direct `w11/r12 -> w11/r12` conversion.

## Batch

```text
batches/ema200_rsi_1h_edge_phase2c_width_atr_timeframe_sensitivity_fee04.json
```

## Candidate folder

```text
candidates/phase2c_width_atr_timeframe_sensitivity/
```

## Matrix

### Base controls

Selected final Phase 2B candidates are kept as base ATR controls:

```text
2.15 + w11/r12/lb20
2.15 + w11/r12/lb10
2.35 + w11/r12/lb20
2.35 + w11/r12/lb10
2.45 + w11/r12/lb20
2.45 + w11/r12/lb10
2.45 + w10/r11/lb20  # profit lane, not main
```

Total base controls:

```text
7
```

### 1h ATR width sweep

Width ATR timeframe:

```text
1h
```

Current width values:

```text
2.0
2.5
3.0
3.5
4.0
4.5
5.0
```

Recent width:

```text
current + 0.25
current + 0.50
```

Lookbacks:

```text
lb10
lb20
lb35
```

Rails:

```text
2.15
2.35
2.45
```

Total 1h-width candidates:

```text
7 current values × 2 recent deltas × 3 lookbacks × 3 rails = 126
```

Total batch:

```text
126 + 7 = 133 candidates
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2c_width_atr_timeframe_sensitivity_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2c_width_atr_timeframe_sensitivity_fee04.json
```

## If validation fails

If the config validator rejects:

```text
anchor_stack_width_setup.atr_timeframe = 1h
```

do not silently change the configs.

Stop and implement / expose non-base ATR timeframe support for `anchor_stack_width_setup` in the backend/catalog first.

This is a feature-contract issue, not a research-result issue.

## What to compare

Do not select only by PnL.

Compare 1h-width candidates against base controls by:

```text
PF
PnL
win rate
maxDD
trade count
long PF
short PF
PF symmetry gap
long/short PnL
fees paid
stop_loss_after_bad_context
stop_loss_after_low_mfe
high_mfe_high_capture_count
high_mfe_low_capture_count
```

## Good outcome

1h ATR width normalization is interesting if it produces:

```text
similar or better PF than base controls
similar or better win rate
better PF symmetry
stable trade count
lower bad-context stops
lower maxDD
not only short-side improvement
```

## Bad outcome

Reject 1h ATR width as main ruler if:

```text
it only works at one isolated threshold
it collapses trade count
it becomes one-side-only
it works only on 2.45 transition rail
it has worse PF symmetry than base controls
it improves PnL only by increasing DD
```

## Expected decision

After Phase 2C, choose one of:

```text
A. Keep base ATR width normalization:
   Phase 3 RSI 1h diagnostics should use Phase 2B core.

B. Switch to 1h ATR width normalization:
   Phase 3 RSI 1h diagnostics should use new Phase 2C 1h-width core.

C. Keep both:
   base ATR width = local pullback geometry
   1h ATR width = higher-volatility context comparator
```
