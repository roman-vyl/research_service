# EMA200 Runner Exit Research — consolidated findings

Status: after fee04 RSI runner rerun and Phase 2A EMA loss-of-momentum tests.

Fee model used in the latest focused runs:

```text
fees = 0.0004 one-way
```

## Core architecture caveat

Current tested exits are still mostly `exit_policy` / always-on signal exits.

Current tested runner mechanism:

```text
entry
-> initial SL / initial TP / signal exits are active
-> ADX/DI can move trade to runner phase
-> take_profile_switch disables initial TP after runner
-> signal exits remain generic exit_policy exits
```

So the current RSI and EMA tests are not yet true phase-gated runner-only exits.

Correct interpretation:

```text
tested now:
  ADX runner + disable initial TP + always-on signal exits

target architecture:
  ADX runner + disable initial TP + runner-only managed exits
```

## Key discovery

The major discovery is not simply that RSI90 is good or EMA100/200 is good.

The important discovery:

```text
RSI90/10 and EMA100/200 cross solve different halves of the runner-exit problem.
```

Observed contrast in Phase 2A:

```text
ADX40 runner + RSI90:
  runner exit mix:
    12 RSI exits
    11 stop_loss exits

ADX40 runner + EMA100/200 cross:
  runner exit mix:
    20 EMA exits
    3 stop_loss exits
```

This is strategically important.

RSI90 captures extreme momentum/tail events, but about half of runner trades still fall back to initial SL.

EMA100/200 cross exits many more runner trades before they fall to initial SL, acting more like a loss-of-momentum protective exit.

## Best fee04 RSI candidate

```text
strict_continuation_sl6_tp14
ADX40 -> runner
disable initial TP at runner
RSI5m p14 90/10
fees 0.0004
```

Metrics:

```text
Total PnL: 13 685
PF: 1.452
WR: 37.2%
DD: -0.333

Long PF: 1.244
Short PF: 1.773

Runner trades: 23
Runner PnL: 14 908
Runner PF: 3.843
Runner exit mix:
  RSI90 signal: 12
  initial SL: 11
```

Interpretation:

```text
Best money candidate so far.
But runner protection is weak:
almost half of runner trades still die at initial SL after TP is disabled.
```

## Best Phase 2A EMA candidate

```text
strict_continuation_sl6_tp14
ADX40 -> runner
disable initial TP at runner
EMA100/200 cross signal exit
fees 0.0004
```

Metrics:

```text
Total PnL: 11 386
PF: 1.423
DD: -0.404

Runner trades: 23
Runner PnL: 14 024
Runner PF: 10.414
Runner exit mix:
  EMA100/200 cross: 20
  initial SL: 3
```

Interpretation:

```text
Not as rich as RSI90 by total PnL.
But much cleaner as a runner-protection mechanism.
It dramatically reduces runner -> initial SL failures.
```

## Why this matters

The comparison suggests a combined exit architecture:

```text
after runner:
  keep RSI90/10 as extreme take / momentum exhaustion exit
  replace initial SL with EMA100/200 cross as protective loss-of-momentum exit
```

This potentially kills two problems at once:

```text
1. RSI captures the biggest momentum spikes.
2. EMA100/200 prevents many non-RSI runner trades from giving back everything to initial SL.
```

## Important rejected / deprioritized findings

### Naive hard BE at entry

Rejected as universal action.

Reason:

```text
ADX/DI correctly identifies strong protected/runner-like cohorts,
but hard BE at entry often closes after large MFE back at entry/fees.
```

Conclusion:

```text
ADX/DI is better interpreted as runner selector, not simple BE trigger.
```

### RSI-only

Weak.

Strict fee04 examples:

```text
initial: PnL 2 639, PF 1.357
RSI85 control: PnL 674, PF 1.108
RSI90 control: PnL 1 522, PF 1.220
```

Relaxed fee04 examples:

```text
initial: PnL 2 286, PF 1.122
RSI85 control: PnL -277, PF 0.983
RSI90 control: PnL 1 090, PF 1.061
```

Conclusion:

```text
RSI is not an entry/ordinary-exit edge by itself.
It becomes valuable only in the ADX runner / disabled TP context.
```

### EMA close-loss exits

Mostly rejected in always-on form.

Reason:

```text
EMA close-loss exits trigger too early before runner,
cutting the strategy before the runner hypothesis is tested.
```

### Fast EMA crosses

Potentially interesting later, but not first priority.

Reason:

```text
fast crosses such as EMA20/50 are cleaner than close-loss,
but still too early/noisy as always-on exits.
```

## Current working hypothesis

The next real hypothesis:

```text
ADX40 identifies runner trades.
Initial TP should be disabled after runner.
Initial SL should not remain the only fallback.
Runner phase should use two complementary exits:

1. RSI90/10 for extreme momentum take.
2. EMA100/200 cross for loss-of-momentum protective exit.
```

## Research priority

Do not run another wide always-on sweep yet.

Next step should be architectural:

```text
implement phase-gated runner-only exits / runtime exits
```

Then test:

```text
runner-only RSI90
runner-only EMA100/200
runner-only RSI90 OR EMA100/200
runner-only RSI90 take + EMA100/200 protective exit
```
