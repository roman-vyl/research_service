# Unified Execution Loop v1

## Purpose

This change composes the already ported execution slices into the first complete Research-owned bar-by-bar state machine for one strategy instance.

```text
StrategyEvaluationResult
+ MarketFrame
+ ExecutionPolicy
+ optional managed replay provider
→ research_execution_loop.v1
```

No legacy BBB module is imported or executed.

## Exact legacy ordering preserved

The old `run_managed_execution_loop` used this order on each candle:

1. remember whether a position was open at bar start;
2. evaluate and execute exits for that position;
3. only if the bar started flat, evaluate a new entry;
4. do not update or execute management for a position opened on the current bar.

The new loop preserves the same invariants:

- an entry cannot exit on its entry candle;
- a position that closes on a candle blocks replacement entry on that same candle;
- a new entry can occur on a later candle that begins flat;
- one strategy instance has at most one open position.

## Managed policy integration

The loop accepts an optional transport-neutral managed replay provider:

```text
PositionState
→ ManagedReplayResult | None
```

The provider is called once when a position opens. `ManagedPolicyTimeline` then applies Strategy Engine end-of-bar decisions only on their `effective_from_time_ms` candle. The loop never recalculates phases, managed stops, take switches or runtime exits.

The future single-instance backtest orchestrator will implement this provider through `StrategyEnginePort.evaluate_managed_replay()`.

## Output contracts

### `PositionExecution`

Contains the immutable opened `PositionState` and either:

- `status=open`, with no exit; or
- `status=closed`, with the selected `ExitFill` and full `ExitArbitrationResult`.

### `ExecutionEvent`

The loop emits deterministic events:

- `entry_filled`;
- `exit_filled`;
- `position_left_open`.

Exit events retain layer, rule/component attribution and losing candidate types for later diagnostics.

### `ExecutionLoopResult`

Contains:

- contract version `research_execution_loop.v1`;
- market identity;
- ordered position executions;
- ordered execution events;
- optional final open position.

## End-of-range behavior

Legacy reporting represented a remaining position as open and marked it with the last close for display. The new execution layer does not fabricate an exit fill. It preserves the position as explicitly open; later accounting/report projection may use the last close as a mark price without treating it as realised PnL.

## Out of scope

This slice does not calculate:

- fees;
- realised or unrealised PnL;
- equity;
- MFE/MAE;
- trade metrics;
- artifacts;
- HTTP backtest responses.

Those belong to `research-trade-accounting-v1` and later orchestration changes.
