# Next rerun plan — fee modes before expanding strategy grid

## Reason

Current promising variants were run with:

```text
fees_rate = 0.0006
```

This is conservative. Before adding EMA-cross exits or RSI period/timeframe sweeps, rerun the same Phase 1 candidates under more realistic fee modes.

## Rerun fee modes

Run exactly the same logical Phase 1 grid with:

```text
fees_rate = 0.0004
fees_rate = 0.0003
```

Keep existing 0.0006 result as stress mode.

## Do not change yet

For the next rerun, do not change:

```text
symbol: BTCUSDT
timeframe: 5m
anchor_stack: 100/200/496
trigger: touch_anchor
setups: strict and relaxed branches
ADX thresholds: 40 and 45
RSI period: 14
RSI thresholds: 85/15 and 90/10
```

The goal is not a new search. The goal is to answer:

```text
Are the current runner/RSI findings robust to realistic fee assumptions?
```

## Minimal rerun grid

Use only focused candidates:

```text
strict initial control
relaxed initial control
strict ADX40 runner disable TP RSI85/15
strict ADX40 runner disable TP RSI90/10
strict ADX45 runner disable TP RSI90/10
relaxed ADX40 runner disable TP RSI90/10
relaxed ADX45 runner disable TP RSI90/10
```

For each fee mode:

```text
fees_rate = 0.0004
fees_rate = 0.0003
```

Optional stress-retain:

```text
fees_rate = 0.0006
```

## Required report columns

For each candidate:

```text
trades
net_pnl
profit_factor
win_rate
max_drawdown
long_profit_factor
short_profit_factor
fees_paid
gross_pnl
exit_reason_mix
runner_trade_count
runner_pnl
runner_profit_factor
runner_win_rate
runner_exit_mix
initial_risk_pnl
initial_risk_profit_factor
```

## Required interpretation checks

### 1. Is it both-side?

Reject or quarantine candidates where:

```text
long PF > 1 but short PF < 1
or short PF > 1 but long PF < 1
```

unless the candidate is explicitly marked side-specific.

### 2. Is the edge broad or runner-only?

Classify each candidate:

```text
broad_edge:
  initial_risk PF close to or above 1
  runner improves result but does not carry everything

runner_tail_edge:
  initial_risk negative
  runner cohort carries all profit
```

Runner-tail edge is not rejected, but it requires outlier/year diagnostics.

### 3. Does RSI exit actually matter?

Check:

```text
RSI exit trade count
RSI exit PnL
RSI exits after runner vs before runner
runner exit mix
```

If RSI exits mostly happen before runner, the current config is not truly testing runner-only RSI. In that case, implement phase-gated runtime RSI exit before further sweeps.

### 4. Capture quality

Check runner capture:

```text
avg_capture_ratio
median_capture_ratio
avg_giveback_pct
median_giveback_pct
p75/p90 MFE
```

If capture remains weak, prioritize EMA loss-of-momentum exits or lock-profit rules after fee rerun.

## After fee rerun

Only after reviewing fee-mode results:

```text
Phase 2: RSI period/timeframe refinement
Phase 3: EMA loss-of-momentum exits
Phase 4: very-fast EMA crossing fast/anchor
Phase 5: combined runner stack
```

Do not start Phase 2 until this file is updated with the fee-rerun conclusion.
