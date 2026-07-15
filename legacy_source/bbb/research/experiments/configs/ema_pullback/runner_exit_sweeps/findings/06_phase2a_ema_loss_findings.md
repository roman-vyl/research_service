# Phase 2A EMA loss-of-momentum findings

Batch:

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_runner_ema_loss_phase2a_fee04.json
```

Fee model:

```text
fees = 0.0004
```

## Summary table

| Candidate | Trades | PnL | PF | WR | DD | Long PF | Short PF | Runner trades | Runner PnL | Runner PF | Median capture | Avg giveback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| strict initial | | | | | | | | | | | | |
| runner no-signal ADX40 | | | | | | | | | | | | |
| runner RSI90 reference | | | | | | | | | | | | |
| EMA20 close c2 control | | | | | | | | | | | | |
| EMA20 close c2 runner | | | | | | | | | | | | |
| EMA50 close c2 control | | | | | | | | | | | | |
| EMA50 close c2 runner | | | | | | | | | | | | |
| EMA100 close c2 control | | | | | | | | | | | | |
| EMA100 close c2 runner | | | | | | | | | | | | |
| EMA200 close c2 control | | | | | | | | | | | | |
| EMA200 close c2 runner | | | | | | | | | | | | |
| EMA20x50 c1 control | | | | | | | | | | | | |
| EMA20x50 c1 runner | | | | | | | | | | | | |
| EMA20x100 c1 control | | | | | | | | | | | | |
| EMA20x100 c1 runner | | | | | | | | | | | | |
| EMA50x100 c1 control | | | | | | | | | | | | |
| EMA50x100 c1 runner | | | | | | | | | | | | |
| EMA50x200 c1 control | | | | | | | | | | | | |
| EMA50x200 c1 runner | | | | | | | | | | | | |
| EMA100x200 c1 control | | | | | | | | | | | | |
| EMA100x200 c1 runner | | | | | | | | | | | | |

## Conclusions

### Keep

- 

### Reject

- 

### Needs follow-up

- 

## Notes

Check especially whether signal exits fire before runner. If yes, the exit is not a clean runner exit and needs phase-gated runtime implementation later.
