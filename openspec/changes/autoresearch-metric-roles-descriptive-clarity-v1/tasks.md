## 1. Pre-implementation checks

- [x] 1.1 Re-confirmed live against `scripts/autoresearch_quality_contracts.py:640-679` immediately
      before writing the materializer. One correction found: `ROBUSTNESS_PRIMARY` has **6** members
      (`validation_evidence, neighborhood_stability, realised_trade_count, thinning,
      temporal_concentration, regime_concentration`), not 4 as design.md originally stated (fixed).
      Materializer reads the constant directly, so this was a design-doc wording error only, not a
      code bug.
- [x] 1.2 `MetricRoleSelection` (new `ExactModel`): `primary_evidence_additions: list[str] = []`,
      `promotion_gates: list[GateId] = []`, both required-but-defaultable, uniqueness-checked.
      Uniform shape across all stage kinds -- empty for `descriptive_baseline`/no-optional-evidence
      stages, populated otherwise.
- [x] 1.3 Grepped whole codebase (`scripts/`, `src/`, tests excluded): no caller of
      `MetricRoles`/`StageAssessment` outside `autoresearch_quality_contracts.py` and
      `autoresearch_supervisor.py` (only via `describe_stage_metric_role_contract` import). No
      breakage risk found.

## 2. Deterministic metric_roles materializer

- [x] 2.1 Added `_METRIC_ROLES_FIXED_CORE` (one dict, keyed by `stage_kind`, referencing
      `BASELINE_PRIMARY_ALLOWED`/`EXIT_PRIMARY`/`ROBUSTNESS_PRIMARY` directly for `primary_core`,
      plus the audited fixed `secondary`/`descriptive` sets) and `materialize_metric_roles()` in
      `scripts/autoresearch_quality_contracts.py` -- one shared function, no per-branch copies.
- [x] 2.2 `materialize_metric_roles(stage_kind, selection)` unions `selection.primary_evidence_additions`
      with the stage's `primary_core`; `descriptive_baseline`'s `descriptive` is computed as
      `CANONICAL_METRIC_PATHS - primary` (the `None` sentinel case); every other stage's
      `secondary`/`descriptive` is the fixed set from design.md.
- [x] 2.3 Manually verified (all 6 stage kinds) that materializer output passes the unchanged
      `validate_metric_roles()` unmodified -- confirmed by direct invocation against
      `descriptive_baseline`, `structural_entry`, `structural_interaction`, `exit_geometry`,
      `robustness_validation`. No bypass; formal unit tests added in section 4.

## 3. Worker-facing contract narrowing

- [x] 3.1 `MetricRoleSelection` (uniform shape: `primary_evidence_additions`, `promotion_gates`,
      both defaulting to `[]`) covers every stage kind; per-stage semantics (which fields carry
      real content) are explained in the prompt text (3.2), not encoded as different Pydantic
      shapes per stage -- simpler and matches this codebase's existing pattern of one shape + prompt
      guidance (e.g. `scientific_proposal`'s `values` field is meaningful differently per stage but
      is a single shape).
- [x] 3.2/3.3 `describe_stage_metric_role_contract()` retired and replaced with
      `describe_metric_role_selection_contract()` in `scripts/autoresearch_quality_contracts.py`,
      reading the exact same constants (`CONDITIONAL_ENTRY_EVIDENCE`/`SAMPLE_THINNING_EVIDENCE`/
      `SIDE_BEHAVIOR_EVIDENCE`/`ROBUSTNESS_PRIMARY_ALLOWED - ROBUSTNESS_PRIMARY`) -- one
      worker-facing rendering, no separate copy. `autoresearch_supervisor.py`'s
      `render_interpretation_prompt` now calls the renamed function; `interpretation.md`'s prompt
      text itself needs no edit since it already renders `{stage_metric_role_contract}` generically
      -- only what that placeholder resolves to changed.
- [x] 3.4 (new, not in original plan) Wired the materialization step itself into
      `scripts/autoresearch_supervisor.py`'s `validate_iteration_result`, immediately before
      `validate_assessment()`: pops `stage.metric_role_selection` from the raw worker-submitted
      dict, calls `materialize_metric_roles(stage_kind, selection)`, injects the result as
      `stage.metric_roles` -- in place, on the same dict object reused by `_advance_state()`
      downstream (confirmed by reading `_advance_state`'s `assessment =
      result["research_quality_assessment"]` -- same object, no disk round-trip needed; the
      on-disk `iteration_result.json` permanently keeps the worker's original narrow
      `metric_role_selection`, and resume/recovery re-derives `metric_roles` deterministically
      from it every time `validate_iteration_result` runs, including on crash-recovery replay).

## 4. Tests

- [x] 4.1 `test_materialize_metric_roles_matches_existing_fixture_for_every_stage` (parametrized
      over 5 non-baseline stage kinds) confirms round-tripping each existing fixture through
      `_as_worker_submitted`/`materialize_metric_roles` reproduces it exactly.
      `descriptive_baseline` intentionally excluded -- materializer now always emits the full
      `BASELINE_PRIMARY_ALLOWED` set, not the fixture's old minimal choice (documented divergence,
      not a bug).
- [x] 4.2 `test_materialize_metric_roles_descriptive_baseline_needs_no_worker_input` -- empty
      `MetricRoleSelection()` alone produces a complete, valid `MetricRoles` for this stage.
- [x] 4.3 `test_materialize_metric_roles_rejects_selection_missing_required_evidence`
      (parametrized over the 3 structural stage kinds) -- an empty selection (no required
      evidence named) is rejected by the unchanged `validate_metric_roles`, proving the
      independent validator still catches an invalid worker selection.
- [x] 4.4 `test_glm_smoke_duplicate_metric_failure_is_structurally_eliminated` -- confirms the
      materialized result has no `descriptive`/`primary`/`secondary` overlap, and that
      `MetricRoleSelection` has no `descriptive`/`secondary` attribute at all (nothing to
      duplicate into, structurally).
- [x] 4.5 Full targeted AutoResearch test suite: 143 passed (up from 133 baseline; +10 new tests),
      0 failed. Also updated 2 pre-existing supervisor-level tests
      (`test_v2_supervisor_validates_and_durably_projects_full_assessment`,
      `test_missing_optional_canonical_economic_fact_rejects_promotion_cleanly`) to submit
      `metric_role_selection` via the new `_as_worker_submitted` test helper, and 2 prompt-content
      tests (`test_interpretation_prompt_renders_stage_metric_role_contract_for_baseline`/
      `..._for_v3_session`) to assert the new narrowed prompt wording.

## 5. Verification

- [ ] 5.1 Controlled HOST smoke re-running the same shape of interpretation that failed
      (`A_CONTROL` -> `B1_WIDTH` first entry -> `B1_WIDTH` interpretation) on a worker profile,
      confirming interpretation no longer fails on the `metric_roles` pattern observed in session
      `ema-anchor-glm52-b1-smoke-20260905160326`, and confirming the narrowed worker contract
      produces a valid assessment end to end.
- [x] 5.2 `openspec validate --strict --changes autoresearch-metric-roles-descriptive-clarity-v1`
      passed (7/7).

## 6. Deferred follow-up findings (record only, do not implement here)

- [x] 6.1 Recorded in `proposal.md` (Why, What Changes, Impact) and `design.md` (Non-Goals):
      `GateResult` inside `economic_viability` is almost entirely harness-derivable from
      `policy.promotion_thresholds` + `candidate_facts` -- candidate for its own materializer
      change.
- [x] 6.2 Recorded in `proposal.md`/`design.md`: `experiment`/`execution_result` blocks
      near-verbatim duplicate `canonical_request.json`/`execution_receipt.json`.
- [x] 6.3 Recorded in `proposal.md`/`design.md`: `hypothesis`/`market_property_proxy` are already
      partially materialized post-hoc by `_materialize_interpretation_identity` -- candidate to
      stop asking the worker to author them at all.
- [x] 6.4 Recorded in `proposal.md`/`design.md`: `TradeoffDimension.assessment` for metric-based
      dimensions is partially harness-derivable.
