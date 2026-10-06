## Why

The Calculate parity gate compares the Engine run summary with the metrics stored in
the row at a relative tolerance of 1e-6. Replay result tables store metrics rounded
(fractions and profit factor to 4 decimals, R to 2, net PnL to whole units). On the
smoke run of five replay rows every Engine value, rounded to the stored precision,
equals the stored value and the trade count matches, yet all five rows fail the gate.
The gate cannot tell rounding from a real difference because the table does not say
how its values were rounded.

## What Changes

- A metric of the Experiment result schema MAY declare `decimals`: the number of
  decimal places the table builder rounded that metric to.
- For a metric with `decimals = d` the gate passes when
  `|actual − expected| ≤ ½ × 10^−d` (plus a 1e-9 floating-point allowance).
- A metric without `decimals` keeps the current rule; `integer` metrics stay exact.
- The tolerance stays fixed by these rules and is not a setting; `decimals` describes
  the stored data, not a tolerance.

## Impact

- `research_service.domain.experiment_schema.Metric`: optional `decimals` (integer 0..12).
- `adapters/experiments/run_calculation.py`: parity uses `decimals` when present.
- Manifests: replay Experiments that should pass Calculate add `decimals` to their
  metrics. Engine Experiments written at full precision need no change.
