# EMA200 Runner Exit Sweeps — Phase 2A EMA loss-of-momentum

Fee model:

```text
fees = 0.0004
```

## Why this phase

Phase 1 showed that `ADX40 -> runner + disable initial TP + RSI5m 90/10` is a strong signal on the strict branch, but capture is weak: RSI90 captures the large tail, yet often gives back a lot before exit.

Phase 2A tests EMA-based loss-of-momentum exits as a possible replacement/complement for RSI90.

## Scope

This is intentionally **strict branch only**:

```text
strict_continuation_sl6_tp14
EMA stack 100/200/496
width w12/r14/lb20
untouched75/active8
SL6 / TP14
fees 0.0004
```

Reason: strict already has both-side edge. Relaxed remains noisier and three relaxed fee04 runner reports are still missing, so EMA exit discovery should not start there.

## Tested exit ideas

### EMA close loss

Long exits when close is below EMA for `confirm_bars=2`; short mirrors.

```text
EMA20 close-loss c2
EMA50 close-loss c2
EMA100 close-loss c2
EMA200 close-loss c2
```

### EMA cross loss

Long exits when fast EMA crosses below slow EMA; short mirrors. `confirm_bars=1`.

```text
EMA20 x EMA50
EMA20 x EMA100
EMA50 x EMA100
EMA50 x EMA200
EMA100 x EMA200
```

This covers:

```text
veryfast -> fast
veryfast -> anchor-ish
fast -> anchor-ish
fast -> EMA200 anchor
anchor-stack fast -> anchor
```

## Controls

The batch includes:

```text
initial SL6/TP14 reference
ADX40 runner disable TP no-signal
ADX45 runner disable TP no-signal
Phase 1 RSI90 runner reference
EMA exit without runner controls
EMA exit + ADX40 runner variants
```

This is critical because EMA exits are still normal `exit_policy` signal exits, not phase-gated runtime exits. So every EMA signal must be compared against a non-runner control.

## Run

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_runner_ema_loss_phase2a_fee04.json
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_runner_ema_loss_phase2a_fee04.json
```

## What to compare

Primary question:

```text
Does EMA exit improve runner capture versus RSI90 without killing tail PnL?
```

Compare against:

```text
strict initial fee04
strict ADX40 runner RSI90 fee04 reference
strict ADX40 runner no-signal fee04
```

Metrics:

```text
net PnL
PF
winrate
max DD
long PF / short PF
runner trade count
runner PnL / PF
runner capture summary
runner exit mix
RSI/EMA signal exits before runner vs after runner
```

## Expected interpretation

Good EMA candidate:

```text
PF >= RSI90 reference or close
DD <= RSI90 reference
runner PnL stays high
median capture improves materially
both-side PF remains > 1
```

Bad EMA candidate:

```text
high winrate but much lower PnL
many signal exits before runner
runner PnL collapses
short side breaks
```
