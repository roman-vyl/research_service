## 1. Deterministic relation materializer

- [ ] 1.1 Add `TradeoffComparisonSelection` (`ExactModel`): `left_subject_ref`, `right_subject_ref`,
      `stage_kind`, `dimensions` (`list[TradeoffDimension]`, `min_length=1`) -- no `relation` field.
- [ ] 1.2 Add `derive_tradeoff_relation(dimensions: list[TradeoffDimension]) -> str` implementing the
      exact total mapping in design.md, checked by hand against every branch of
      `relation_is_pareto_consistent`.
- [ ] 1.3 Wire materialization into `scripts/autoresearch_supervisor.py`'s `validate_iteration_result`,
      same try block as the existing `metric_role_selection` materialization: for each raw comparison
      in `raw_assessment["tradeoff_summary"]["comparisons"]`, parse as `TradeoffComparisonSelection`,
      compute `relation`, inject it, before `validate_assessment()`.
- [ ] 1.4 Confirm the compiled `tradeoff_summary` still passes the unchanged
      `relation_is_pareto_consistent` unmodified -- no bypass.

## 2. Prompt fixes (schema exception + subject-ref scope)

- [ ] 2.1 Add an explicit exception to `interpretation.md`'s "the schema wins" rule for
      `tradeoff_summary.comparisons[].relation` -- schema shows it, worker must not write it.
- [ ] 2.2 Add explicit guidance: `left_subject_ref`/`right_subject_ref` must both be candidates from
      the current iteration's own batch (or the current `promotion_subject.region_id`); a comparison
      against a historical baseline (e.g. `A_CONTROL`) belongs in
      `structural_promise.baseline_comparison`, not `tradeoff_summary`.

## 3. Tests

- [ ] 3.1 New unit test: `derive_tradeoff_relation` produces the correct relation for representative
      assessment-value combinations, including the exact failing pattern from the smoke
      (`{left_better, left_better, right_better, left_better, uncertain}` -> `"tradeoff"`, not
      `"left_dominates"`).
- [ ] 3.2 New unit test: a `TradeoffComparisonSelection` submission containing `relation` is rejected
      (via `ExactModel`'s `extra="forbid"`), before materialization is even attempted.
- [ ] 3.3 New unit test: materialized comparisons pass the unchanged `relation_is_pareto_consistent`
      for every representative assessment-value combination (equivalent, left_dominates,
      right_dominates, tradeoff, incomparable).
- [ ] 3.4 Regression test: reconstruct the exact smoke failure pattern
      (`ema-anchor-sonnet-metricroles-smoke-20260905202722`, comparison #0's dimensions) through
      `validate_iteration_result` and confirm it now produces a valid, accepted assessment.
- [ ] 3.5 Full targeted AutoResearch test suite passes after this change.

## 4. Verification

- [ ] 4.1 Controlled HOST smoke, same shape (`A_CONTROL` -> `B1_WIDTH` first entry -> `B1_WIDTH`
      interpretation), confirming interpretation no longer fails on either
      `relation_is_pareto_consistent` or the vs-`A_CONTROL` `subject_refs` misuse pattern observed in
      `ema-anchor-sonnet-metricroles-smoke-20260905202722`. Stop at the first new blocker, if any.
- [ ] 4.2 Confirm `openspec validate --strict` passes for this change before archiving.
