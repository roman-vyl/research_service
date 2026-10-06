## Why

The Calculate parity gate compares the Engine run summary with the row's stored
metrics at a relative tolerance of 1e-6. Legacy replay Surfaces store metrics rounded:
fractions and profit factor to 4 decimals, cumulative R to 2, and `net_pnl` derived as
the rounded return × 10 000. On the 5-row smoke (35 cells) the trade count matched
exactly and 29 float cells failed the gate; every one of them equals the stored value
at the stored precision. The failures are lost precision in the legacy artifact, not
an Engine difference, and the strict gate cannot be met by any legacy row.

## What Changes

- A second, explicit gate `legacy_surface` that compares the Engine value at the
  precision the legacy Surface actually holds, with fixed rules per Engine summary
  field:
  - `realised_trade_count`: exact integer.
  - `return_pct`, `profit_factor`, `win_rate`, `max_drawdown`: `round(engine, 4) == stored`.
  - `cumulative_net_r`: `round(engine, 2) == stored`.
  - `net_pnl`: `|engine − stored| ≤ 0.5`.
- An Experiment opts in with `materialize.parity: "legacy_surface"`. The default is
  `strict`, the existing gate, unchanged.
- No per-metric precision in the manifest, no precision read from the cell text, no
  tolerance setting.

## Impact

- `domain/experiment_materialize.py`: `MaterializeBlock.parity: Literal["strict", "legacy_surface"] = "strict"`.
- `adapters/experiments/run_calculation.py`: the gate dispatches on `parity`.
- Engine Experiments and new Surfaces stored at full precision keep the strict gate.
