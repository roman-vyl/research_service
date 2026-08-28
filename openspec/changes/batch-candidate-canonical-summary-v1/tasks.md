## 1. Contracts

- [ ] 1.1 Add `BatchSideSummary` (`trades`, `net_pnl`, `return_pct`,
      `win_rate | None`, `profit_factor | None`) to
      `application/experiments/contracts.py`.
- [ ] 1.2 Extend `BatchCandidateResult` with `return_pct`,
      `win_rate | None`, `profit_factor | None`, `max_drawdown`,
      `long: BatchSideSummary | None`, `short: BatchSideSummary | None`
      (`None` on failed candidates only).

## 2. Derivation

- [ ] 2.1 Add a pure derivation function (module-level, no I/O) taking
      `accounting.trades` + `accounting.initial_equity` and returning the
      six new scalar/side-summary fields, per `design.md` formulas.
- [ ] 2.2 Call it from `_settle_candidate` in `run_batch.py` immediately
      after successful persist, before building the returned
      `BatchCandidateResult`.

## 3. Tests

- [ ] 3.1 Unit tests for the derivation function: zero trades, all
      winners, all losers, mixed, break-even trade excluded from
      `win_rate`, single-side-only trade sets.
- [ ] 3.2 Batch-level test: failed candidate row has no new fields
      populated; successful candidate row's new fields match a
      hand-computed expectation from a small fixed trade list.

## 4. Spec

- [ ] 4.1 `openspec archive batch-candidate-canonical-summary-v1` after
      implementation lands and tests pass.
