## 1. Metric

- [x] 1.1 `TradeMetric` gains `mfe_r`; `ManagedTradeState` holds the
      frozen `initial_risk` and the incremental advance carries it
      forward. Verify: `tests/test_managed_mfe_r.py` covers both sides,
      the unit of the threshold, a position without a stop and the
      incremental state against the eager timeline (the test that
      caught initial risk being dropped on advance).
- [x] 1.2 `make verify` is green (ruff, mypy, full suite).
- [x] 1.3 `openspec validate mfe-r-phase-threshold-v1 --strict` passes.
