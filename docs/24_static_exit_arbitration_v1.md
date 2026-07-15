# Static exit arbitration v1

## Purpose

This slice rebuilds the Research-owned static exit behavior that followed Strategy Engine decisions in the legacy BBB execution loop.

## Inputs

- `PositionState.initial_protection` resolved on entry;
- Strategy Engine `exit_policy.signal_exit` for the position side;
- the aligned MDS candle for the current bar.

## Candidate semantics

- stop loss: gap through the level fills at open; otherwise touch fills at the level;
- take profit: gap through the level fills at open; otherwise touch fills at the level;
- signal exit: fills at close.

The entry bar is skipped because the old loop evaluated exits before opening a new position at that bar's close.

## Same-bar policy

`v1` preserves the reviewed ordering:

1. `stop_loss`;
2. `take_profit`;
3. `signal`.

Losing candidates are retained for attribution and future diagnostic projections.

## Deferred

Managed stop/take/runtime-exit candidates are not part of this slice. They will be consumed from Strategy Engine managed replay and merged into a single arbitrator later.
