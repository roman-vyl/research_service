# Design

## Inputs

- `StrategyEvaluationResult` static policy series;
- `PositionState.initial_protection`;
- current MDS `Candle`;
- optional `ManagedEffectiveState` inherited for the current bar.

## Candidate collection

Static and managed collectors remain focused adapters. The unified collector passes `active_take_profile` to the static collector. The exact profile `disable_initial_tp` suppresses only the initial fixed take-profit candidate.

## Arbitration

The deterministic v1 order is:

1. `stop_loss`;
2. `managed_stop`;
3. `take_profit`;
4. `runtime_protective`;
5. `runtime_take`;
6. `runtime_close` / `runtime_exit`;
7. `signal`.

Candidates from different bars must be rejected.

## Output

The winner becomes one canonical `ExitFill`. Layer, rule ID, component ID and exit kind are preserved for later attribution and diagnostics. Losing candidates remain on `ExitArbitrationResult`.
