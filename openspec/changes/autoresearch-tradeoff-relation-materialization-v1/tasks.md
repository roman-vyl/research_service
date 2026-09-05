## 1. Deterministic relation materializer

- [x] 1.1 Added `TradeoffComparisonSelection` in `scripts/autoresearch_quality_contracts.py`.
- [x] 1.2 Added `derive_tradeoff_relation()`. Manually verified against 10 representative
      assessment-value combinations (all 5 relation outcomes + edge cases with `uncertain`) plus
      the exact smoke failure pattern -- every result constructs a valid `TradeoffComparison`
      without `relation_is_pareto_consistent` raising.
- [ ] 1.3 Wire materialization into `scripts/autoresearch_supervisor.py`'s `validate_iteration_result`,
      same try block as the existing `metric_role_selection` materialization: for each raw comparison
      in `raw_assessment["tradeoff_summary"]["comparisons"]`, parse as `TradeoffComparisonSelection`,
      compute `relation`, inject it, before `validate_assessment()`.
- [ ] 1.4 Confirm the compiled `tradeoff_summary` still passes the unchanged
      `relation_is_pareto_consistent` unmodified -- no bypass.

## 2. Prompt fixes (schema exception + subject-ref scope)

- [x] 2.1 Added explicit exception to `interpretation.md`'s "the schema wins" rule for
      `tradeoff_summary.comparisons[].relation` -- schema shows it, worker must not write it.
- [x] 2.2 Added explicit guidance: `left_subject_ref`/`right_subject_ref` must both be candidates
      from the current iteration's own batch (or the current `promotion_subject.region_id`); a
      comparison against a historical baseline (e.g. `A_CONTROL`) belongs in
      `structural_promise.baseline_comparison`, not `tradeoff_summary`. Verified rendered prompt
      (`render_interpretation_prompt`) is internally consistent, no contradiction.

## 3. Tests

- [x] 3.1/3.3 `test_derive_tradeoff_relation_matches_pareto_consistency_for_every_case`
      (parametrized, 10 cases) confirms `derive_tradeoff_relation` produces the correct relation
      for every representative assessment-value combination, including the exact smoke pattern
      (`{left_better, left_better, right_better, left_better, uncertain}` -> `"tradeoff"`), and that
      each result constructs a valid `TradeoffComparison` under the unchanged
      `relation_is_pareto_consistent`.
- [x] 3.2 `test_tradeoff_comparison_selection_rejects_worker_supplied_relation` -- a submission
      containing `relation` is rejected during `TradeoffComparisonSelection.model_validate()`.
- [x] 3.4 `test_sonnet_smoke_tradeoff_relation_mismatch_is_materialized_correctly` -- reconstructs
      the exact smoke failure pattern through `validate_iteration_result` (full supervisor path,
      not just the direct validator), confirms it is now accepted with the correctly materialized
      `relation: "tradeoff"`.
- [x] 3.5 Full targeted AutoResearch test suite: 155 passed (up from 143 baseline; +12 new tests),
      0 failed.

## 4. Verification

- [ ] 4.1 Controlled HOST smoke, same shape (`A_CONTROL` -> `B1_WIDTH` first entry -> `B1_WIDTH`
      interpretation), confirming interpretation no longer fails on either
      `relation_is_pareto_consistent` or the vs-`A_CONTROL` `subject_refs` misuse pattern observed in
      `ema-anchor-sonnet-metricroles-smoke-20260905202722`. Stop at the first new blocker, if any.
- [ ] 4.2 Confirm `openspec validate --strict` passes for this change before archiving.
