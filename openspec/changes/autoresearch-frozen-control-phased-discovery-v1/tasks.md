## 1. Stage contract core (`scripts/autoresearch_stage_contracts.py`)

- [x] 1.1 Bump `STAGE_CONTRACT_VERSION` (v1 -> v2) so old 4-stage sessions fail closed against the
      new contract, per design.md Migration Plan.
- [x] 1.2 Rename `STAGES` to the 6-tuple `(A_CONTROL, B1_WIDTH, B2_LOOKBACK,
      B3_WIDTH_X_LOOKBACK, C_ENTRY_REGION_SELECTION, D_EXIT_GEOMETRY)`; update every reference.
- [x] 1.3 `STAGE_PHASES` maps `A_CONTROL -> "baseline"` (unchanged phase string, already bound to
      `descriptive_baseline` in the template), `C_ENTRY_REGION_SELECTION -> "entry_region_selection"`,
      `D_EXIT_GEOMETRY -> "exit_geometry"` (exact `StageKind` strings, both already present in the
      template's `phase_bindings`).
- [x] 1.4 Remove `symmetric_measurement_geometry` from `A_CONTROL`'s `STAGE_DIMENSIONS` (Phase A
      no longer varies any dimension); keep `B1_WIDTH`/`B2_LOOKBACK`/`B3_WIDTH_X_LOOKBACK`
      dimensions unchanged.
- [x] 1.5 Remove `measurement_geometries`/`geometry_references` from the stage contract's
      `A_CONTROL` shape (design.md Decision 2); `A_CONTROL`'s single measured value is the
      existing `starting_strategy.resolved_sha256`.
- [x] 1.6 Fix `required_stages` in `validate_stage_context`: `B2_LOOKBACK` depends only on
      `A_CONTROL`, not on `B1_WIDTH` -- B1 and B2 are independent branches, neither a prerequisite
      of the other (design.md Revision note item 1 / Decision 4's corrected graph). `B3_WIDTH_X_LOOKBACK`
      requires both `B1_WIDTH` and `B2_LOOKBACK` durably closed.
- [x] 1.7 Add `PROVISIONAL_STAGES = (C_ENTRY_REGION_SELECTION, D_EXIT_GEOMETRY)` and make
      `validate_stage_context` reject any plan targeting either with an explicit "execution
      semantics are not yet defined" error, before it would otherwise look up
      `STAGE_DIMENSIONS`/`required_stages` (neither has an entry for either stage) (design.md
      Decision 3).
- [x] 1.8 `autoresearch_supervisor.py`'s `validate_state` additionally rejects a durable state whose
      `active_stage` is already a `PROVISIONAL_STAGES` member (defense in depth against a
      hand-edited `state.json`), and its per-stage closed-prerequisite checks match the corrected
      B1/B2-independent graph.
- [x] 1.9 `_advance_state`'s stage-transition logic never sets `active_stage` to either provisional
      stage: closing B3 leaves `active_stage` at `B3_WIDTH_X_LOOKBACK`; a worker proposing no
      further experiment reaches ordinary terminal `completed` status from there, not a transition.
- [x] 1.10 Confirm no code path can set `exit_management.mode: "managed"` for any stage in this
      capability; `managed_policy_enabled` continues to be derived `false` by the existing
      harness-owned derivation (already true independent of stage; no change needed, verified by
      existing tests).

**Explicitly removed from this change's scope** (see design.md Revision note item 2 and Decision 3):
defining `entry_region_selection`'s shortlist acceptance rule or state shape; defining
`exit_geometry`'s per-region distance-sweep or reference-hash mechanism; any `entry_regions` state
field. These require real B1/B2/B3 evidence shape to design against and belong in a follow-up
change.

## 2. Quality contracts (`scripts/autoresearch_quality_contracts.py`)

No changes. `entry_region_selection`/`exit_geometry` metric-role contracts remain
defined-but-unreachable, exactly as before this change -- reachability is explicitly deferred to
the follow-up change that defines those stages' execution semantics (see section 1).

## 3. Prompts and templates

- [x] 3.1 Update `autoresearch/prompts/planning.md`: new stage names, frozen-control framing
      (Phase A measures once, does not scan or optimize exit geometry; B1/B2/B3 hold that same
      frozen exit fixed).
- [x] 3.2 Explain `prerequisite_disposition_refs` semantics explicitly in `planning.md` (closes the
      gap found in the smoke that motivated this change) -- done via `_stage_authority_context()`
      (`scripts/autoresearch_supervisor.py`), which prints the exact stage, mutable/frozen
      dimensions, and `expected_prerequisite_disposition_refs()` value directly into
      `{stage_authority_context}` in `planning.md`; B1/B2 additionally get explicit
      independent-baseline framing, B3 gets explicit evidence-guided joint-search framing. Both the
      validator and the prompt read the same `REQUIRED_STAGES`/`expected_prerequisite_disposition_refs`
      source, so they cannot drift.
- [x] 3.3 Update `autoresearch/program.md`: causal-sequence description corrected to "A control ->
      B1/B2 independent branches -> B3 interaction (requires both)", frozen-control framing,
      version-string fix (`bbb_autoresearch_stage_contract.v2`). The EMA-anchor domain skill
      (`.claude/skills/ema-anchor-edge-research/SKILL.md`) has no stage-name-specific content and
      needed no change.
- [x] 3.4 Update `autoresearch/templates/ema_anchor_stage_contract_session.json`: single frozen
      3.0/3.0 ATR control instead of `measurement_geometries: [A-2, A-3, A-4]`.
- [x] 3.5 Update `autoresearch/fixtures/ema_anchor_100_200_500_naked.json`'s exit multiplier to 3.0
      for readability (cosmetic -- it is always overridden by the configured geometry at
      request-build time, so this was never behavioral).

## 4. Schemas

- [x] 4.1 Update `autoresearch/schemas/stage_contract.schema.json`: new stage enum values, removed
      `measurement_geometries`/`geometry_references` shape entirely (not replaced by anything for
      the reserved stages).
- [x] 4.2 Update `autoresearch/schemas/execution_plan.v2.schema.json`,
      `autoresearch/schemas/session_state.v3.schema.json`,
      `autoresearch/schemas/iteration_result.v3.schema.json`,
      `autoresearch/schemas/journal_event.v3.schema.json`,
      `autoresearch/schemas/stage_session_template.schema.json` to match (new stage enum values,
      dropped `geometry_id`/`reference_strategy_sha256`/`measurement_geometries` fields).

## 5. Supervisor plumbing (`scripts/autoresearch_supervisor.py`)

- [x] 5.1 `phase_a_references`/`stage_history`/journal-event shapes drop per-geometry keying
      (`geometry_id`/`distance`); `phase_a_references` becomes a 0-or-1-entry list (Phase A
      measures once) instead of a geometry-keyed collection.
- [x] 5.2 Confirm `_materialize_interpretation_identity`, `_session_scoped_experiment_id`, and
      `_with_derived_managed_policy_enabled` need no changes (they operate on experiment/candidate
      identity, not stage dimensions) -- confirmed via the full existing regression suite passing
      unchanged.

**Deferred**: any `region_id`-aware stage-context/geometry plumbing for `D_EXIT_GEOMETRY` -- moot
until that stage's contract is defined (section 1).

## 6. Tests

- [x] 6.1 `tests/test_autoresearch_stage_contract.py`: rewritten for the single-control model and
      the corrected B1/B2-independent graph; tests for the `A_CONTROL` single-value invariant.
- [x] 6.2 Tests for the frozen-control-under-B1/B2/B3 invariant (exit distance never varies in
      structural stages).
- [x] 6.3 Tests that B2_LOOKBACK is reachable without B1_WIDTH closed
      (`test_b2_lookback_does_not_require_b1_width_closed`), and that B3 still requires both.
- [x] 6.4 Tests that `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` are unreachable
      (`test_c_and_d_are_unreachable_provisional_stages`) even once every prior stage is durably
      closed.
- [ ] 6.5 `tests/test_autoresearch_quality_policy.py`: no new coverage needed or added --
      `entry_region_selection`/`exit_geometry` metric-role contracts remain untestable end to end
      by design (deferred, not a gap in this change).
- [x] 6.6 Confirmed `tests/test_autoresearch_program_contract.py` has no stage-name-specific
      assertions; no update needed.
- [x] 6.7 Full targeted AutoResearch test suite, Ruff, and `git diff --check` pass after each part
      of this change.

## 7. Verification

- [ ] 7.1 Run a controlled HOST research run (not capped at one iteration) through
      `A_CONTROL -> B1_WIDTH` and `A_CONTROL -> B2_LOOKBACK` independently, confirming both are
      reachable without the other closed, and that B3 correctly requires both.
- [ ] 7.2 Once real B1/B2/B3 evidence exists from 7.1, open the follow-up change that defines
      `entry_region_selection`/`exit_geometry`'s durable state shape and execution semantics
      (design.md Open Questions) -- informed by evidence, not designed blind.
- [ ] 7.3 Before or during that follow-up change, consciously decide (operator, not silently
      assumed) whether B3 eligibility is strict (both B1 and B2 must find a promising region) or
      exploratory (either's `terminally_rejected` is still sufficient) -- see design.md Open
      Questions; the current mechanism is exploratory by construction, not by deliberate choice.
