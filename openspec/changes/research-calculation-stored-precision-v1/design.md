## Context

`research-run-calculation-v1` fixed a hard tolerance (rel 1e-6, abs 1e-9) and made it
non-configurable. Engine result tables store full precision and pass it. Replay tables
store rounded values, so they cannot pass it even when the Engine reproduces the
replay exactly.

## Decisions

### D1. Precision is declared, not guessed

The number of decimals is part of the result schema metric (`decimals`), written by
whoever builds the table. Guessing from the cell text is rejected: builders write
values rounded to whole units as `8861.0`, which reads as one decimal.

### D2. Half a unit of the last stored decimal

A stored value rounded to `d` decimals stands for every true value within
`½ × 10^−d` of it, so that is the exact bound; `1e-9` is added for floating-point
representation. No wider band is allowed.

### D3. Absent `decimals` keeps the current rule

Existing Engine Experiments and their behaviour do not change. `integer` metrics are
always compared exactly; `decimals` on an `integer` metric is rejected.

## Risks

- A wrong `decimals` in a manifest widens or narrows the gate for that metric. It is
  visible in the manifest and reported in `parity_failed` diagnostics (the rule used
  per metric).
