## 1. Derivation function

- [x] 1.1 Add `_cumulative_risk_outcome(n: int, wr: Decimal | None) -> Decimal` in
      `src/research_service/application/experiments/candidate_summary.py`: `n == 0` -> `Decimal("0")`;
      else defensive `0 <= wr <= 1` (`ValueError` otherwise); else `Decimal(n) * (2 * wr - 1)`.
- [x] 1.2 Wire into `_side_summary()` (pass `len(trades)` and the already-computed `win_rate`) and
      into `derive_batch_candidate_summary()` (aggregate, same pattern) -- reuse the win_rate value
      already computed in each function, do not call `_win_rate` twice.

## 2. Contract fields

- [x] 2.1 Add `cumulative_risk_outcome: Decimal` to `BatchSideSummary`
      (`src/research_service/application/experiments/contracts.py:90-101`).
- [x] 2.2 Add `cumulative_risk_outcome: Decimal | None = None` to `BatchCandidateResult`
      (`contracts.py:104-137`), and add `"cumulative_risk_outcome"` to both `_SUMMARY_FIELDS` and
      `_SUMMARY_FIELDS_REQUIRED_ON_COMPLETION` (`contracts.py:29-30`).
- [x] 2.3 Pass `cumulative_risk_outcome=` through at every `BatchCandidateResult(...)` construction
      site in `src/research_service/application/experiments/run_batch.py` (lines ~168, ~207, ~219)
      that also sets `return_pct`/`max_drawdown` today, sourcing it from the same
      `BatchCandidateSummary` the other derived fields already come from.

## 3. EvidenceRef allowlist

- [x] 3.1 Add `"cumulative_risk_outcome"`, `"long.cumulative_risk_outcome"`,
      `"short.cumulative_risk_outcome"` to `CANONICAL_METRIC_PATHS` in
      `scripts/autoresearch_quality_contracts.py`.

## 4. Tests

- [x] 4.1 Unit tests for `_cumulative_risk_outcome`: `n == 0` -> `Decimal("0")`; representative
      `(n, wr)` pairs match `Decimal(n) * (2*wr - 1)` exactly (Decimal, no float); `wr` outside
      `[0, 1]` raises `ValueError`.
- [x] 4.2 Test on `derive_batch_candidate_summary`/`_side_summary` fixtures: aggregate
      `cumulative_risk_outcome` equals `long.cumulative_risk_outcome + short.cumulative_risk_outcome`
      for a fixture with trades on both sides; a fixture with zero trades on one side reports that
      side's `cumulative_risk_outcome: 0`.
- [x] 4.3 `BatchCandidateResult`/`BatchSideSummary` model tests: `cumulative_risk_outcome` required
      when `status == "completed"`, forbidden (via existing `validate_summary_shape`) when
      `status == "failed"`.
- [x] 4.4 `EvidenceRef` test: `canonical_metric` with `metric_path="cumulative_risk_outcome"` (and
      the `long.`/`short.` variants) parses successfully; confirm `_metric()` resolves the new paths
      against a `candidate_facts`-shaped fixture with no code change to `_metric()` itself.
- [x] 4.5 Full repo test suite: 463 passed, 0 failed (up from 461 baseline; +2 net after fixing 3
      pre-existing fixtures that needed the new required field and adding the two model-shape tests).

## 5. Verification

- [x] 5.1 Produced a real `execution_output.json` fragment (via the real `execute_batch()` adapter,
      real `derive_batch_candidate_summary()` computation, mocked only at the Engine/persist service
      boundary) showing `cumulative_risk_outcome` physically present next to `realised_trade_count`/
      `win_rate`, including `long`/`short`.
- [x] 5.2 `openspec validate --strict --changes autoresearch-cumulative-risk-outcome-v1` passes (9/9
      changes, 0 failed).
