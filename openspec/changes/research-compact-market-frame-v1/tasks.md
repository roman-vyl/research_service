## 1. Baseline

- [x] 1.1 Measure candle memory (tracemalloc) and value shape (decimal places, maxima) for the full window.
- [x] 1.2 Baseline wall time and peak RSS for one fixed SL/TP run (`ratio_4d`) and one managed trailing run (`trailing_geometry_fee4_4d`); confirm current code reproduces their stored artifacts byte for byte.

## 2. Implementation

- [x] 2.1 Columnar `MarketFrame` with lossless coefficient + exponent arrays and a read-only `candles` sequence view.
- [x] 2.2 Decode MDS JSON straight into the arrays; keep the grid validation.
- [x] 2.3 Adapt only the consumers that need more than index, length, iteration or slicing.
- [x] 2.4 Unit tests: exact `Decimal` round-trip including exponent (`6500` vs `6500.0`, volume with 8 places), slicing, negative index, grid errors.

## 3. Acceptance

- [x] 3.1 Re-run the two reference runs on the new code: `trades.json`, `execution_events.json`, `strategy_evaluation.json`, `managed_policy_events.json`, `metrics.json` byte-identical to the stored ones (run id aside).
- [x] 3.2 Peak RSS and wall time before/after for both runs, in the PR description.
- [x] 3.3 `make verify`; `openspec validate --all --strict`.
