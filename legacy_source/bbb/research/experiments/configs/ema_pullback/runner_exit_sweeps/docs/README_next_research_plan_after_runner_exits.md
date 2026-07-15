# EMA200 Research Plan — next directions after phase-gated runner exits

## Context

The current best strict runner candidates are:

```text
money mode:
  strict_adx40_runner_only_rsi90_fee04

balanced mode:
  strict_adx40_runner_only_rsi88_12_fee04

defensive mode:
  strict_adx40_runner_rsi90_plus_ema100_200_fee04

protective baseline:
  strict_adx40_runner_only_ema100_200_fee04
```

The main unresolved issue:

```text
strict setup has edge, but trade count is sparse.
Runner exits work, but many trades never reach runner.
Some runner trades produce big tails, some return to emergency SL.
```

Therefore the next research should be layered, not one giant sweep.

---

## Step 0 — setup universe comparison

Before adding partial take / BE / trailing, compare the same runner exit logic across setup profiles:

```text
strict
relaxed
loose_probe
```

Goal:

```text
Find whether a larger trade universe exists with acceptable edge.
```

Important: do not judge only total PnL. Inspect:

```text
trade count
PF
avg trade
avg win / avg loss
long PF / short PF
runner trades
runner PnL
non-runner TP / SL
drawdown
```

A relaxed setup is useful if it gives more trades without turning the strategy into fee/noise churn.

---

## Step 1 — bucket decomposition report

Before changing mechanics, decompose every candidate into buckets:

```text
non-runner initial TP
non-runner SL
runner RSI exit
runner EMA exit
runner emergency SL
open trades
```

For each bucket:

```text
count
PnL
avg win
avg loss
avg trade
hold time
side breakdown
year breakdown
```

Purpose:

```text
Understand where money is made and where leakage happens.
```

This answers:

```text
How many trades never become runner but still take initial TP?
How much damage comes from non-runner SL?
How much damage comes from runner emergency SL?
Does runner edge pay for non-runner losses?
```

---

## Step 2 — partial take management

Hypothesis:

```text
RSI90 captures fat tails, but some runner trades return to emergency SL.
EMA protects too aggressively and cuts tails.
Partial take may keep RSI90 tail upside while monetizing part of the move earlier.
```

First v1 idea:

```text
after runner:
  if initial TP level is touched:
    close fraction of position
    keep remaining position open for RSI90 / RSI88 / emergency SL
```

Fractions:

```text
0.25
0.33
0.50
```

Test matrix:

```text
RSI90-only
RSI90 + partial 25%
RSI90 + partial 33%
RSI90 + partial 50%

RSI88-only
RSI88 + partial 25%
RSI88 + partial 33%
RSI88 + partial 50%
```

Acceptance:

```text
lower runner emergency SL damage
preserve most of RSI90 tail PnL
improve drawdown or year stability
do not collapse avg win too much
```

Architecture warning:

```text
Partial take is not just a component.
It requires position legs / remaining size / partial fill events / weighted PnL.
Do this via OpenSpec, not quick patch.
```

---

## Step 3 — break-even / lock stop

Do not use naive BE immediately at runner. Previous reasoning showed it can turn potential tails into zero/fee losses.

Better candidates:

```text
BE after MFE >= 1R
BE after MFE >= 1.5R
BE after initial TP level touched
lock entry + fees
lock entry + 0.25 ATR
lock entry + 0.5 ATR
```

Best order:

```text
partial TP first
then BE/lock on remaining position
```

Reason:

```text
Partial take monetizes movement.
BE only protects; it does not create profit.
```

---

## Step 4 — trailing candidates

Potential trailing components:

```text
MFE giveback trailing
ATR trailing
Chandelier-style trailing
EMA trailing stop
swing-low / swing-high trailing
```

Most aligned with current diagnostics:

```text
mfe_giveback_trailing_stop
```

Example:

```text
after runner:
  track best price / MFE
  if MFE >= 2 ATR:
    exit if giveback >= 35% of MFE
```

or:

```text
exit if price gives back 1.5 ATR from best runner price
```

Purpose:

```text
Keep more tail than EMA-cross, but prevent full return to emergency SL.
```

---

## Step 5 — larger trade universe

Separate from exit mechanics, search for 250–400 trade candidates.

Levers:

```text
width:
  current 12 -> 10 / 9 / 8
  recent 14 -> 12 / 10 / 9
  lookback 20 -> 30 / 40

untouched:
  lookback 75 -> 50 / 40 / 30
  active_bars 8 -> 10 / 12 / 15

anchor:
  EMA200 keep as baseline
  later test EMA150 / EMA250 / EMA300

trigger:
  touch_anchor
  reclaim_anchor
  strong_reclaim_anchor
```

Acceptance:

```text
more trades
PF > 1.25
avg trade positive after fees
long and short not both dominated by one side only
year-by-year not concentrated in one lucky period
```

---

## Recommended order

```text
0. setup universe comparison: strict vs relaxed vs loose_probe
1. bucket decomposition report
2. partial take management
3. RSI90 vs RSI88 year-by-year
4. BE/lock stop on remaining position
5. MFE/giveback trailing
6. broader setup sweep for 250–400 trades
```

Main principle:

```text
Do not mix entry-universe expansion with new execution mechanics in one sweep.
```
