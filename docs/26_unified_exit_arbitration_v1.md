# Unified exit arbitration v1

This slice reconstructs the exact Research-owned half of the legacy `ExitArbitrator` seam.

## Flow

```text
static policy candidates
+ managed policy candidates
+ inherited active take profile
→ deterministic same-bar arbitration
→ ExitFill
```

Strategy Engine still owns all policy decisions. Research Service owns OHLC hit detection, candidate collection, winner selection and fill construction.

## Compatibility order

```text
stop_loss
→ managed_stop
→ take_profit
→ runtime_protective
→ runtime_take
→ runtime_close/runtime_exit
→ signal
```

`active_take_profile=disable_initial_tp` removes only the initial fixed TP candidate before arbitration. It does not remove managed/runtime take candidates.

## Scope boundary

This slice does not yet iterate over a full market range or close `PositionState`. That state-machine orchestration is the next change: `research-unified-execution-loop-v1`.
