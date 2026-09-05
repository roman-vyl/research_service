## 1. Pre-implementation checks

- [ ] 1.1 Grep `tests/test_autoresearch_quality_policy.py` and any HOST smoke
      `var/autoresearch/*/iterations/*/iteration_result.json` on disk for a non-empty
      `metric_roles.descriptive` value. Record findings; if any exist, resolve explicitly
      (legitimate value this design's "always empty" assumption must account for, vs. an existing
      never-caught mistake this fix should now catch) before tightening the validator.
- [ ] 1.2 Re-confirm (quick re-read) that `validate_metric_roles()`'s four stage-kind branches
      (`descriptive_baseline`, `structural_entry`/`structural_interaction`/
      `entry_region_selection`, `exit_geometry`, robustness fallback) genuinely never reference
      `roles.descriptive` today -- the exact basis for this change's "always empty" design decision.

## 2. Cheat-sheet text

- [ ] 2.1 Add an explicit `metric_roles.descriptive` statement to each of
      `describe_stage_metric_role_contract()`'s four stage-kind branches
      (`scripts/autoresearch_quality_contracts.py:592-637`), stating it must be empty for that
      stage, worded consistently across branches.
- [ ] 2.2 If a shared constant/helper reduces duplication across the four branches (per design.md's
      "one shared source of truth" decision), introduce it; otherwise four consistent inline
      statements are acceptable.

## 3. Mechanical validator

- [ ] 3.1 Add a matching check to `validate_metric_roles()` for each of its four stage-kind
      branches: `roles.descriptive` must be empty, raising a clear `ValueError` (e.g.
      `"metric_roles.descriptive must be empty for this stage"`) if not.
- [ ] 3.2 Confirm the new check's error message is distinguishable from the existing disjointness
      error (`"metric roles must be disjoint"`) so a future failure log clearly identifies which
      rule fired.

## 4. Tests

- [ ] 4.1 New unit test: `describe_stage_metric_role_contract()`'s rendered text for each stage
      kind explicitly mentions `descriptive` and states it must be empty.
- [ ] 4.2 New unit test: `validate_metric_roles()` rejects a `research_quality_assessment` whose
      `metric_roles.descriptive` is non-empty, for each of the four stage kinds, with the new
      distinguishable error message.
- [ ] 4.3 New unit test: `validate_metric_roles()` still accepts a correct assessment with
      `metric_roles.descriptive == []` for each stage kind, mirroring existing passing fixtures in
      `tests/test_autoresearch_quality_policy.py` (no regression to already-valid assessments).
- [ ] 4.4 Regression test: construct the exact failure pattern from the `glm52-opencode` HOST smoke
      (a `structural_entry` assessment with an economics metric duplicated into both `descriptive`
      and `secondary`) and confirm it is now rejected with the new, clearer error rather than the
      generic disjointness error -- demonstrating the fix targets the actual observed failure mode.
- [ ] 4.5 Full targeted AutoResearch test suite (`tests/test_autoresearch_quality_policy.py` and any
      other test file exercising `autoresearch_quality_contracts.py`) passes after this change.

## 5. Verification

- [ ] 5.1 Controlled HOST smoke re-running the same shape of interpretation that failed
      (`A_CONTROL` -> `B1_WIDTH` first entry -> `B1_WIDTH` interpretation) on a worker profile,
      confirming interpretation no longer fails on the `metric_roles` disjointness pattern
      observed in session `ema-anchor-glm52-b1-smoke-20260905160326`. (A different failure, if one
      occurs, is out of scope for this change to fix, but should be recorded.)
- [ ] 5.2 Confirm `openspec validate --strict` passes for this change before archiving.
