## 1. Stage contract core (`scripts/autoresearch_stage_contracts.py`)

- [ ] 1.1 Bump `STAGE_CONTRACT_VERSION` (and any other version constants whose shape changes) so
      old 4-stage sessions fail closed against the new contract, per design.md Migration Plan.
- [ ] 1.2 Rename `STAGES` to the 6-tuple `(A_CONTROL, B1_WIDTH, B2_LOOKBACK,
      B3_WIDTH_X_LOOKBACK, C_ENTRY_REGION_SELECTION, D_EXIT_GEOMETRY)`; update every reference.
- [ ] 1.3 Update `STAGE_PHASES` to map `A_CONTROL -> "control"`,
      `C_ENTRY_REGION_SELECTION -> "entry_region_selection"`,
      `D_EXIT_GEOMETRY -> "exit_geometry"` (exact `StageKind` strings).
- [ ] 1.4 Remove `symmetric_measurement_geometry` from `A_CONTROL`'s `STAGE_DIMENSIONS` (Phase A
      no longer varies any dimension); keep `B1_WIDTH`/`B2_LOOKBACK`/`B3_WIDTH_X_LOOKBACK`
      dimensions unchanged.
- [ ] 1.5 Add `STAGE_DIMENSIONS` entries for `C_ENTRY_REGION_SELECTION` (none -- shortlisting is a
      selection over B3 output, not a new candidate dimension) and `D_EXIT_GEOMETRY`
      (`symmetric_measurement_geometry`, now scoped per shortlisted region).
- [ ] 1.6 Remove `measurement_geometries`/`geometry_references` from the stage contract's
      `A_CONTROL` shape (design.md Decision 2); `A_CONTROL`'s single measured value is the
      existing `starting_strategy.resolved_sha256`.
- [ ] 1.7 Add `entry_regions` state list (region_id, width range, lookback range, structural
      evidence refs, accepted iteration) per design.md Decision 4; do not repurpose
      `phase_a_references`.
- [ ] 1.8 Add `D_EXIT_GEOMETRY`'s configured value set keyed by `(region_id, geometry_id,
      distance)` with published reference hashes, per design.md Decision 3; generalize
      `reference_strategy(state, geometry_id)` to `reference_strategy(state, region_id,
      geometry_id)` that composes the frozen naked baseline + that region's width/lookback +
      that geometry's distance.
- [ ] 1.9 Extend `validate_stage_context`'s `required_stages` mapping with
      `C_ENTRY_REGION_SELECTION: {A_CONTROL, B1_WIDTH, B2_LOOKBACK, B3_WIDTH_X_LOOKBACK}` and
      `D_EXIT_GEOMETRY: {..., C_ENTRY_REGION_SELECTION}` (design.md Decision 5).
- [ ] 1.10 Add stage-contract validation for the shortlist size bound (1-3 regions) when accepting
      `entry_region_selection` output.
- [ ] 1.11 Ensure no code path can set `exit_management.mode: "managed"` for `D_EXIT_GEOMETRY`
      candidates; `managed_policy_enabled` continues to be derived `false` by the existing
      harness-owned derivation.

## 2. Quality contracts (`scripts/autoresearch_quality_contracts.py`)

- [ ] 2.1 Verify `describe_stage_metric_role_contract` and `validate_metric_roles` for
      `entry_region_selection`/`exit_geometry` are exercised end to end now that stages reach
      them (no new logic expected -- confirm via tests in section 5).

## 3. Prompts and templates

- [ ] 3.1 Update `autoresearch/prompts/planning.md`: new stage names, explain
      `prerequisite_disposition_refs` semantics explicitly (closes the gap found in the smoke that
      motivated this change), explain the `entry_region_selection` shortlist contract (1-3
      regions), explain `D_EXIT_GEOMETRY`'s per-region distance sweep and its published reference
      hashes.
- [ ] 3.2 Update `autoresearch/prompts/interpretation.md`: stage-aware guidance for
      `entry_region_selection` (shortlist justification) and `exit_geometry` (economics-now-primary
      framing, matching the existing quality-policy requirement).
- [ ] 3.3 Update `autoresearch/program.md` and the EMA-anchor domain skill: causal-sequence
      description (A control -> B1/B2 independent -> B3 interaction -> C shortlist -> D exit
      geometry), explicit "no managed exits yet" boundary.
- [ ] 3.4 Update `autoresearch/templates/ema_anchor_stage_contract_session.json`: single frozen
      3.0/3.0 ATR control instead of `measurement_geometries: [A-2, A-3, A-4]`.
- [ ] 3.5 Update `autoresearch/fixtures/ema_anchor_100_200_500_naked.json` (or confirm no change
      needed) so its exit distance matches the new frozen control value.

## 4. Schemas

- [ ] 4.1 Update `autoresearch/schemas/stage_contract.schema.json`: new stage enum values, removed
      `A_CONTROL` geometry-scan shape, new `D_EXIT_GEOMETRY` per-region reference-hash shape, new
      `entry_regions` shape.
- [ ] 4.2 Update `autoresearch/schemas/execution_plan.v2.schema.json` (and any other schema
      referencing stage names) to match.

## 5. Supervisor plumbing (`scripts/autoresearch_supervisor.py`)

- [ ] 5.1 Generalize any stage-context/geometry-id plumbing that assumes `symmetric_measurement_geometry`
      is the only scannable dimension to also carry `region_id` for `D_EXIT_GEOMETRY`.
- [ ] 5.2 Confirm the existing `_materialize_interpretation_identity`, `_session_scoped_experiment_id`,
      and `_with_derived_managed_policy_enabled` mechanisms need no changes (they operate on
      experiment/candidate identity, not stage dimensions) -- add a regression test asserting this
      if any of them touch stage-shaped data.

## 6. Tests

- [ ] 6.1 `tests/test_autoresearch_stage_contract.py`: update fixtures for the renamed/added
      stages; add tests for the `A_CONTROL` single-value invariant (Requirement: "Phase A freezes
      exit geometry as a single control, not a scan").
- [ ] 6.2 Add tests for the frozen-control-under-B1/B2/B3 invariant (exit distance never varies in
      structural stages).
- [ ] 6.3 Add tests for `entry_region_selection` shortlist acceptance (1-3 regions, unsupported
      spike rejected) and for `D_EXIT_GEOMETRY`'s per-region distance sweep and reference-hash
      publication.
- [ ] 6.4 Add tests for the new `required_stages` causal-order rows (cannot enter
      `entry_region_selection`/`exit_geometry` before prerequisites close).
- [ ] 6.5 `tests/test_autoresearch_quality_policy.py`: add coverage for
      `entry_region_selection`/`exit_geometry` metric-role contracts now being reachable (was
      previously untestable end to end because no stage ever reached them).
- [ ] 6.6 `tests/test_autoresearch_program_contract.py`: update causal-order assertions for the new
      six-stage sequence.
- [ ] 6.7 Run the full targeted AutoResearch test suite, Ruff, and `git diff --check` before
      considering this change complete.

## 7. Verification

- [ ] 7.1 Run a controlled HOST smoke on a fresh session through `A_CONTROL` only, confirming the
      single-control-value invariant holds end to end (planning -> batch -> interpretation).
- [ ] 7.2 Run a controlled HOST smoke through `A_CONTROL -> B1_WIDTH` (or as far as budget/time
      allow), confirming exit distance stays fixed and causal-order prerequisites are satisfied.
