## 1. Pre-implementation checks

- [ ] 1.1 Re-confirm each per-stage-kind fixed value and worker-retained selection from design.md
      against the live `validate_metric_roles()` body one more time immediately before writing the
      materializer (constants may have shifted since this design pass) -- do not trust cached line
      numbers.
- [ ] 1.2 Decide the exact `metric_role_selection` schema/artifact shape (design.md Open Question)
      before writing the materializer signature.
- [ ] 1.3 Confirm no other caller of `MetricRoles`/`StageAssessment` (grep the whole codebase, not
      just this file) assumes a fully worker-authored `metric_roles` object in a way this change
      would break.

## 2. Deterministic metric_roles materializer

- [ ] 2.1 Add a single materializer function keyed on `stage_kind` that builds the deterministic
      core for each of the 5 stage kinds (`descriptive_baseline`, `structural_entry`,
      `structural_interaction`, `entry_region_selection`, `exit_geometry`,
      `robustness_validation` -- 6 total kinds) per the exact fixed values in design.md, reading
      `DESCRIPTIVE_ECONOMICS`/`BASELINE_PRIMARY_ALLOWED`/`STRUCTURAL_PRIMARY_ALLOWED`/
      `CONDITIONAL_ENTRY_EVIDENCE`/`SAMPLE_THINNING_EVIDENCE`/`SIDE_BEHAVIOR_EVIDENCE`/
      `EXIT_PRIMARY`/`ROBUSTNESS_PRIMARY`/`ROBUSTNESS_PRIMARY_ALLOWED`/`CANONICAL_METRIC_PATHS`
      directly -- one source of truth, no per-branch copies.
- [ ] 2.2 Add the worker-selection merge step: union the worker's narrow `metric_role_selection`
      (evidence-set choices for structural stages, optional primary additions for robustness,
      `promotion_gates` for every non-baseline stage) with the deterministic core to build a
      complete `MetricRoles`-shaped object.
- [ ] 2.3 Run the compiled object through the unchanged `validate_metric_roles()` (and the rest of
      `research_quality_assessment` validation) before accepting the assessment -- no bypass, same
      independent post-hoc defense pattern as the planning-side materializer.

## 3. Worker-facing contract narrowing

- [ ] 3.1 Define the exact `metric_role_selection` input the worker submits per stage kind (per
      design.md's per-stage-kind "Worker submits" lines): none for `descriptive_baseline`; 2-3
      evidence-set choices for structural stages; optional primary additions + `promotion_gates`
      for `robustness_validation`; `promotion_gates` only for `exit_geometry`.
- [ ] 3.2 Update `autoresearch/prompts/interpretation.md` (or a narrower prompt surface analogous to
      `autoresearch/prompts/scientific_proposal.md`'s pattern) so the worker is told exactly which
      `metric_role_selection` fields apply to the active stage -- not the full `MetricRoles`
      structure, not a fuller cheat-sheet about `descriptive`.
- [ ] 3.3 Confirm `describe_stage_metric_role_contract()` either becomes the narrower
      "here is exactly what you must select" text per stage, or is retired in favor of prompt text
      generated directly from the same constants the materializer uses (avoid maintaining two
      separate worker-facing renderings of the same policy).

## 4. Tests

- [ ] 4.1 New unit test: for each of the 6 stage kinds, the materializer produces the exact fixed
      core specified in design.md (byte-identical to the existing test fixtures in
      `tests/test_autoresearch_quality_policy.py:121-158` for the fields those fixtures already
      exercise).
- [ ] 4.2 New unit test: for `descriptive_baseline`, the materializer alone (no worker selection
      input) produces a complete `MetricRoles` that passes `validate_metric_roles()` unchanged.
- [ ] 4.3 New unit test: for each structural stage kind, a worker selection naming only one member
      of each required evidence set compiles into a valid `MetricRoles`; a selection naming zero
      members of a required set is rejected by the unchanged `validate_metric_roles()` (proves the
      independent validator still catches an invalid worker selection, not just a materializer bug).
- [ ] 4.4 Regression test: reconstruct the exact `glm52-opencode` HOST smoke failure pattern (an
      economics metric duplicated across roles) and confirm it cannot occur at all under the new
      contract, because the worker no longer authors `secondary`/`descriptive` -- the failure class
      is structurally eliminated, not merely caught with a clearer message.
- [ ] 4.5 Full targeted AutoResearch test suite (`tests/test_autoresearch_quality_policy.py` and any
      other file exercising `autoresearch_quality_contracts.py`) passes after this change.

## 5. Verification

- [ ] 5.1 Controlled HOST smoke re-running the same shape of interpretation that failed
      (`A_CONTROL` -> `B1_WIDTH` first entry -> `B1_WIDTH` interpretation) on a worker profile,
      confirming interpretation no longer fails on the `metric_roles` pattern observed in session
      `ema-anchor-glm52-b1-smoke-20260905160326`, and confirming the narrowed worker contract
      produces a valid assessment end to end.
- [ ] 5.2 Confirm `openspec validate --strict` passes for this change before archiving.

## 6. Deferred follow-up findings (record only, do not implement here)

- [ ] 6.1 File as a future, separate finding: `GateResult` inside `economic_viability` is almost
      entirely harness-derivable from `policy.promotion_thresholds` + `candidate_facts` (same audit,
      this session) -- candidate for its own materializer change.
- [ ] 6.2 File as a future, separate finding: `experiment`/`execution_result` blocks near-verbatim
      duplicate `canonical_request.json`/`execution_receipt.json`.
- [ ] 6.3 File as a future, separate finding: `hypothesis`/`market_property_proxy` are already
      partially materialized post-hoc by `_materialize_interpretation_identity` -- candidate to stop
      asking the worker to author them at all.
- [ ] 6.4 File as a future, separate finding: `TradeoffDimension.assessment` for metric-based
      dimensions is partially harness-derivable.
