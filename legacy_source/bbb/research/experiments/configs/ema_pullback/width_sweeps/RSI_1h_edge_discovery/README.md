# RSI 1h Edge Discovery — Clean Research Track

Folder:

```text
research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/
```

## Goal

This folder is a clean research branch for checking whether the EMA200 pullback edge improves when the measurement / context layer is shifted toward 1h logic.

The immediate focus is not to add RSI as an active filter.

The current focus is:

```text
find a clean 1h ATR symmetric SL/TP ruler
then use that ruler to rediscover / retune width edge
then only later inspect RSI 1h diagnostics
```

## Hard rule

Do not combine too many variables at once.

No active RSI, no ADX runner, no BE, no partial TP, no trailing, no asymmetric rails until the 1h ATR ruler and width zone are understood.

---

# Current phase status

## Phase 0 — coarse 1h ATR symmetric ruler calibration

Batch:

```text
batches/ema200_rsi_1h_edge_phase0_1h_atr_symmetric_ruler_calibration_fee04.json
```

Matrix:

```text
profiles:
  no_width
  known_width_sanity
  relaxed_known
  strict_known

1h ATR symmetric rails:
  0.50
  0.75
  1.00
  1.25
  1.50
  2.00
```

Key findings:

```text
no_width remains bad:
  best no_width 1hATR 2/2:
    PnL -6 748
    PF 0.930
    maxDD -70.7%

known_width_sanity remains not enough:
  best known_width_sanity 1hATR 2/2:
    PnL -1 222
    PF 0.952
    short PF 0.773

best corrected coarse candidate:
  relaxed_known 1hATR 2/2:
    trades 352
    PnL +2 889
    PF 1.087
    win rate 56.5%
    maxDD -19.4%
    long PF 1.139
    short PF 1.037

strict_known 1hATR 2/2:
    trades 140
    PnL +546
    PF 1.051
    long PF 0.936
    short PF 1.223
```

Interpretation:

```text
1h ATR ruler changes the picture.
Relaxed known width becomes the cleaner both-side candidate.
Strict known becomes more short-biased.
```

Phase 0 verdict:

```text
Proceed to finer sweep around 2.0 and above.
```

---

## Phase 0B — 1h ATR fine sweep

Batch:

```text
batches/ema200_rsi_1h_edge_phase0b_1h_atr_symmetric_fine_sweep_fee04.json
```

Matrix:

```text
profiles:
  relaxed_known
  strict_known

1h ATR symmetric rails:
  1.50 to 2.50
  step 0.05
```

Key findings:

```text
best relaxed:
  relaxed_known 1hATR 2.45/2.45:
    trades 350
    PnL +4 946
    PF 1.123
    win rate 56.3%
    maxDD -22.6%
    long PF 1.161
    short PF 1.086
    long PnL +3 205
    short PnL +1 741

second relaxed:
  relaxed_known 1hATR 2.50/2.50:
    trades 347
    PnL +4 745
    PF 1.119
    maxDD -24.3%
    long PF 1.137
    short PF 1.101
```

Strict remains secondary / short-biased:

```text
best strict:
  strict_known 1hATR 2.50/2.50:
    trades 138
    PnL +1 574
    PF 1.119
    long PF 0.989
    short PF 1.318
```

Interpretation:

```text
2.45 is the best observed relaxed ruler.
2.50 is close behind.
The top is still near the upper boundary, so the true optimum may be above 2.50.
```

Phase 0B verdict:

```text
Do not jump to Phase 1 yet.
Run Phase 0C upper guard sweep first.
```

---

## Phase 0C — upper guard sweep

Batch:

```text
batches/ema200_rsi_1h_edge_phase0c_1h_atr_upper_guard_sweep_fee04.json
```

Purpose:

```text
Check whether 2.45/2.50 is a local top
or whether wider 1h ATR symmetric rails keep improving.
```

Matrix:

```text
relaxed_known:
  1h ATR symmetric 2.50 to 3.00
  step 0.05

strict_known sparse controls:
  2.45
  2.50
  2.75
  3.00
```

Total:

```text
11 relaxed candidates
4 strict control candidates
15 total candidates
```

Why strict is sparse:

```text
Strict is not the primary both-side ruler.
It is useful as a control branch because it revealed short-biased behavior.
```

What Phase 0C decides:

```text
If relaxed peaks around 2.45–2.60 and then falls:
  use 2.45 or 2.50 as Phase 1 ruler.

If relaxed keeps improving through 3.00:
  the rail is becoming a wider continuation proxy.
  then decide explicitly whether Phase 1 should use that continuation-style ruler.

If both sides remain PF > 1 near 2.45/2.50:
  relaxed remains primary branch.

If short side collapses or DD expands:
  reject wider values even if PnL improves.
```

---

# Commands

Validate Phase 0C:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0c_1h_atr_upper_guard_sweep_fee04.json
```

Run Phase 0C:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase0c_1h_atr_upper_guard_sweep_fee04.json
```

---

# What to compare

Do not select only by PnL.

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
```

Preferred ruler:

```text
both long and short PF > 1
no large DD expansion
trade count remains stable
PF and PnL are on a plateau, not a one-point spike
```

Reject or mark risky:

```text
only one side carries the result
DD expands materially
larger multiplier just turns into loose continuation holding
PnL improves but PF / side balance deteriorates
```

---

# Current planned order

```text
Phase 0:
  coarse 1h ATR symmetric ruler calibration

Phase 0B:
  fine 1h ATR sweep around 1.50–2.50

Phase 0C:
  upper guard sweep 2.50–3.00

Phase 1:
  current width sweep on selected 1h ATR ruler

Phase 2:
  recent width / lookback sweep

Phase 3:
  asymmetric SL/TP only after width edge is visible

Phase 4:
  RSI 1h bucket diagnostics at entry

Phase 5:
  active RSI 1h gate/filter only if diagnostics justify it
```

---

# Still intentionally excluded

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

This branch is still calibrating the measurement ruler.
