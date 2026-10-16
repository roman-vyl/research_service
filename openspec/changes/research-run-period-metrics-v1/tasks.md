## 1. Summary

- [x] 1.1 Pure functions over the trade list: per-trade return, IS / OOS parts, years, years up, worst year, average
      trade, payoff (D1-D5). Verify: unit tests on synthetic trades (empty list, one part empty, a year with one
      trade, winners only, losers only, the split instant itself).
- [x] 1.2 `BatchCandidateResult` fields (optional) and `BatchYearSummary`; failed candidates must not populate them
      (D8). Verify: contract tests; an old persisted summary still validates.
- [x] 1.3 `period_split_ms` on `BatchExperimentRequest` (default 2023-07-01T00:00:00Z) passed to the summary (D6).
      Verify: test with the default and with a custom split.

## 2. Calculate

- [x] 2.1 `research_policy.period_split_ms` in the materialize block, passed to the batch request. Verify: test.
- [x] 2.2 Result bindings resolve the new fields (`is_net_pnl`, `years.2024.return_pct`, `years_up`, ...).
      Verify: Calculate test with a bound year return.

## 3. Acceptance (owner's Mac, research data, no Engine runs)

- [x] 3.1 Recompute the new fields from the stored trades of the A1 signed surface runs and compare with the replay
      columns of their rows (`is_net_pnl`, `oos_net_pnl`, `return_<year>`, `years_up`, `worst_year`; rounding of the
      table). Report mismatches with cause.
      Mac 2026-10-16: 444 of 444 runs; IS / OOS within 0.005 USD, year returns and worst year within 0.00005 (the table's
      rounding). One row differs in `years_up` (6 against 5): its 2025 return is +0.00004, which the replay rounded to
      0 before counting; Research counts exact returns above 0 (owner's choice, 2026-10-16).
- [x] 3.2 The same for `avg_trade_bp` and `payoff_ratio` against a surface that carries them and has stored runs.
      Mac 2026-10-16: ADX-rise exit Engine runs, EMA500 1999 and EMA1000 1362 runs, 0 mismatches beyond the table's
      rounding (avg trade 0.0005 bp, payoff 0.00005).

## 4. Gate

- [x] 4.1 ruff, mypy, the affected tests.
- [x] 4.2 `openspec validate research-run-period-metrics-v1 --strict`.
