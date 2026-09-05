## 1. Pre-implementation checks

- [x] 1.1 Confirm the exact shape and append-conditions of `state["stage_history"]` in
      `scripts/autoresearch_supervisor.py` (`_advance_state`) -- verify it is appended for every
      committed v3 iteration regardless of disposition status (including `in_progress`), and confirm
      no code path currently reads it for anything this change would conflict with.
      Confirmed (`:2103-2110`): appended unconditionally for every committed v3 iteration inside the
      `contract_version == STATE_VERSION_V3` branch, not gated on disposition status. Only other
      reader is `validate_iteration_control`-adjacent code at `:1159` (iterates it read-only for an
      unrelated check) -- no conflict.
- [x] 1.2 Confirm `_STATE_V3_KEYS` exact-keyset validation in `scripts/autoresearch_supervisor.py`.
      Confirmed: `validate_state` (`:957-968`) calls `_require_exact_keys(state, _STATE_V3_KEYS, ...)`
      -- a strict, not minimum, set match. `stage_initial_sweeps` is added as a **required** key;
      historical session-state compatibility is an explicit non-goal (design.md), so no `.get()`
      fallback, dual-read, or state contract version bump is introduced. A pre-existing v3 session
      missing the key is expected to fail `validate_state` and is not made loadable again.
- [x] 1.3 Confirm whether the bound component for `B1_WIDTH`/`B2_LOOKBACK` can ever already be present
      in a later iteration's "reference" (verify against actual `reference_strategy()` semantics).
      Confirmed (`stage_contracts.py:308-317`): `reference_strategy()` always returns a fresh deep
      copy of the same frozen `stage_contract.starting_strategy.strategy` -- it never incorporates
      any prior iteration's committed choices. The bound component is therefore ALWAYS absent from
      the reference on every materialization call, first-entry or subsequent, for the lifetime of a
      session. The component-insertion function only ever needs the "component absent, insert"
      branch for B1_WIDTH/B2_LOOKBACK in practice; a defensive "already present" check may still be
      added for safety but has no real exercised code path today.
- [x] 1.4 Locate the current exact line number of the output-boundary check in
      `scripts/autoresearch_supervisor.py` and confirm it remains generic on `result_path`.
      Confirmed at `:838-863`. It is fully generic: allowed created paths are exactly `result_path`
      (whatever filename was passed into that specific `runner.run(result_path=...)` call),
      `analysis_dir`'s contents, and `stdout_path`/`stderr_path`/`prompt_path`. `_FORBIDDEN_WORKER_NAMES`
      (`:332`) is `{"uv.lock", "sitecustomize.py", "market.sqlite3"}` -- does not include
      `scientific_proposal.json` or any planning-artifact name. **Finding: no allowlist change is
      needed for a new `scientific_proposal.json` artifact type** -- the materializer simply passes
      `result_path=iteration_root/"scientific_proposal.json"` to the subsequent-entry planning
      worker's `runner.run()` call, exactly as today's planning call passes
      `result_path=iteration_root/"execution_plan.json"`. Task 4.2 is revised accordingly (see below).
- [x] 1.5 Grep for any existing code or test that assumes every `B1_WIDTH`/`B2_LOOKBACK` iteration is
      worker-authored (mirroring task 1.1 from the archived `A_CONTROL` change) -- provenance
      fields, worker-identity logging, retry/attempt bookkeeping. Record findings.
      No hits in `tests/test_autoresearch_supervisor.py` (no existing test references `B1_WIDTH`/
      `B2_LOOKBACK` at all). `tests/test_autoresearch_stage_contract.py`'s B1/B2 fixtures
      (`test_b1_allows_only_width_and_preserves_frozen_control_exit` etc.) test
      `validate_stage_request`/`_strip_allowed` directly against hand-constructed requests, agnostic
      of who produced them -- no conflict with a materializer-produced request.

## 2. `stage_initial_sweeps` state field

- [x] 2.1 Add `stage_initial_sweeps` as a new top-level v3 state key, sourced from the session init
      template. Implemented in `scripts/autoresearch_init.py::initialize_session`: required
      (`raise ValueError` if template lacks it for a v3 session, mirroring `research_quality_policy`),
      validated via new `validate_stage_initial_sweeps()`, copied verbatim into frozen state.
- [x] 2.2 Add `stage_initial_sweeps` to `autoresearch/templates/ema_anchor_stage_contract_session.json`.
      Operator-supplied values: `B1_WIDTH` 5..35 step 5 (`[5,10,15,20,25,30,35]`), `B2_LOOKBACK` 10..200
      step 10 (`[10,20,...,200]`, 20 values). `autoresearch/templates/ema_anchor_session.json` is not
      a v3 template (no `contract_version`/`stage_contract`) and does not need this field.
- [x] 2.3 Add `"stage_initial_sweeps"` to `_STATE_V3_KEYS` in `scripts/autoresearch_supervisor.py`.
      New `validate_stage_initial_sweeps()` enforces the narrow shape (exact keys
      `{"B1_WIDTH","B2_LOOKBACK"}`, each `{"values": [non-empty number list]}`) and is called from
      `validate_state`'s v3 branch, alongside `research_horizon` validation. No `.get()` fallback, no
      dual-read, no state contract version bump.

## 3. Deterministic first-entry materialization

- [x] 3.1 Add a component-insertion function (the missing inverse of `_strip_allowed`) in
      `scripts/autoresearch_stage_contracts.py`. Implemented as `insert_bound_value(strategy,
      contract, dimension, value)`, building `{**fixed_parameters, parameter_name: value}` (nested
      `params_storage` under `"params"`, flat at top level, mirroring `_strip_allowed`'s
      `expected_fixed` construction) and inserting it into `raw_spec["setups"]` when absent, or
      replacing the existing bound instance when present (per 1.3's finding, the replace branch has
      no exercised real-world path today but is implemented defensively).
- [x] 3.2 Add a function that detects "first entry into stage X" from `state["stage_history"]`.
      Implemented as `_is_stage_first_touch(state, stage)`.
- [x] 3.3 Add a function that materializes a `B1_WIDTH`/`B2_LOOKBACK` first-entry `execution_plan.json`.
      Implemented as `_materialize_initial_sweep_plan(state, stage)` in
      `scripts/autoresearch_supervisor.py`, mirroring `_materialize_a_control_plan`. Deterministic
      `candidate_id`s: `"{stage-slug}-{value}"`; `experiment_id`: `"{stage-slug}-initial-sweep"` --
      both pass through the existing `_with_canonical_experiment_id`/`_session_scoped_experiment_id`
      namespacing unchanged. `explanatory_metadata` carries `{"materialized_by": "supervisor",
      "worker": None, "origin": "initial_sweep"}` as the lightweight provenance tag.
- [x] 3.4 Run the materialized first-entry payload through the unchanged `validate_stage_request`/
      `validate_stage_context` path before treating it as frozen -- reuses `_freeze_plan` ->
      `validate_execution_plan` unchanged, identical to the `A_CONTROL` precedent.

## 4. Narrowed scientific_proposal for subsequent entries

- [x] 4.1 Define the exact `scientific_proposal` artifact contract for a subsequent B1/B2 iteration.
      Implemented `validate_scientific_proposal()` and `SCIENTIFIC_PROPOSAL_VERSION =
      "bbb_autoresearch_scientific_proposal.v1"` in `scripts/autoresearch_supervisor.py`. Final field
      list, revised from `proposal.md`'s conceptual shape: `contract_version`, `session_id`,
      `iteration_id`, `hypothesis`, `question`, `competing_explanation`, `values`, `rationale`,
      `expected_information_gain`. Added `competing_explanation` (absent from the original
      conceptual shape) because `execution_plan.v2.schema.json` requires it as a non-empty string
      and it is genuine scientific content (per the earlier field classification review), not
      something the materializer can derive. `market_property_proxy` (also schema-required) is
      NOT part of the proposal -- the materializer sets it deterministically to the stage's bound
      `dimension` name. Artifact filename: `scientific_proposal.json` (see 4.2 -- no allowlist
      change needed).
- [x] 4.2 ~~Add new filename to output-boundary allowlist~~ -- not needed, per 1.4's finding: the
      boundary check is generic on whatever `result_path` is passed to `runner.run()`; pass
      `result_path=iteration_root/"scientific_proposal.json"` for this stage's planning call and it
      is automatically permitted, same as `execution_plan.json` is today for full-form planning.
- [x] 4.3 Add a materializer that consumes the `scientific_proposal` and produces an
      `execution_plan.json`. Implemented as `_materialize_scientific_proposal_plan(state, stage,
      proposal)`, reusing `insert_bound_value` (3.1) -- same component-insertion implementation as
      the first-entry path (3.3), driven by `proposal["values"]` instead of
      `stage_initial_sweeps`. `candidate_id`: `"{slug}-{value}"`; `experiment_id`:
      `"{slug}-iter-{iteration_id}"` (iteration-scoped, so repeated subsequent entries of the same
      stage across a session never collide) -- both namespaced by the existing
      `_with_canonical_experiment_id` path unchanged.
- [x] 4.4 Write a narrowed planning prompt for subsequent B1/B2 iterations. New file
      `autoresearch/prompts/scientific_proposal.md` + `render_scientific_proposal_prompt()` in
      `scripts/autoresearch_supervisor.py`. Drops `batch_request_schema_path`, full
      component-catalog reading, and `stage_context` verbatim copy-paste; keeps program/skill/
      state/journal reading, coarse-to-fine / boundary-resolution / information-dense-batch
      guidance, and `analysis_dir`. Compact stage-authority statement names the one mutable
      dimension directly instead of the full `{stage_context, semantic_bindings, ...}` JSON blob
      `planning.md` requires today. `autoresearch/prompts/planning.md` itself is unchanged --
      `A_CONTROL` and every other stage still route through it exactly as before.
- [x] 4.5 Run every subsequent-entry materialized candidate through the unchanged
      `validate_stage_request`/`validate_stage_context` path before treating it as frozen -- reuses
      `_freeze_plan` -> `validate_execution_plan` unchanged, same as 3.4 and the `A_CONTROL`
      precedent; verified manually against a hand-built proposal before wiring dispatch.

## 5. Supervisor dispatch

- [x] 5.1 Branch planning-stage dispatch for `active_stage in {"B1_WIDTH", "B2_LOOKBACK"}`
      (`_INITIAL_SWEEP_STAGES`) on `_is_stage_first_touch`: first entry -> deterministic
      materialization (`_materialize_initial_sweep_plan`), no worker process; subsequent entry ->
      narrowed `scientific_proposal` retry loop (`render_scientific_proposal_prompt` +
      `validate_scientific_proposal` + `_materialize_scientific_proposal_plan`), mirroring the
      existing full-form retry loop's structure (failure_limit, output-boundary check,
      repository-violation check, repeated-failure hard-stop). Component-catalog fetch is also
      skipped for both first-entry and subsequent-entry `B1_WIDTH`/`B2_LOOKBACK` (extended the same
      guard that already skipped it for `A_CONTROL`) -- binding is frozen for these locked stages,
      the narrowed prompt never references the catalog. The pre-existing unconditional full-form
      planning block is now only reachable for stages outside `{A_CONTROL, B1_WIDTH, B2_LOOKBACK}`
      (i.e. `B3_WIDTH_X_LOOKBACK` and beyond) -- verified by inspection: every `B1_WIDTH`/
      `B2_LOOKBACK` code path above it either advances `control` away from `"planning_pending"` on
      success or returns 2 on failure before reaching it.
- [x] 5.2 Confirm interpretation for both first-entry and subsequent-entry B1/B2 iterations is
      unaffected. Confirmed by inspection: the new dispatch branches only guard the
      `"planning_pending"` control stage; interpretation dispatch code is untouched, identical to
      the `A_CONTROL` precedent's finding.
- [x] 5.3 Confirm `planning_attempts` metadata bookkeeping. First-entry: `planning_attempts` stays
      `[]`, `metadata["planning_materialized"] = True` is set (same marker `A_CONTROL` uses).
      Subsequent-entry: normal attempt bookkeeping via the same `attempts.append({**run.metadata,
      "retry_index": retry, "failure": failure})` pattern as full-form planning.
- [x] 5.4 Confirm no fallback to `stage_initial_sweeps` occurs once a stage has one committed entry.
      By construction: the first-entry branch's guard is `_is_stage_first_touch(...)` (true) and the
      subsequent-entry branch's guard is its negation -- there is no code path that re-checks
      `stage_initial_sweeps` once `state["stage_history"]` contains an entry for that stage,
      including inside the subsequent-entry branch's own retry loop on failure (it only retries the
      same `scientific_proposal` prompt, exactly mirroring the full-form loop's retry behavior).
      Verified with a new unit test (6.5).

## 6. Tests

- [x] 6.1 New unit test: component-insertion function produces the expected `raw_spec` for both the
      component-absent and component-present cases. Added
      `test_insert_bound_value_adds_absent_component_for_b1_and_b2`,
      `test_insert_bound_value_overwrites_present_component`, and
      `test_insert_bound_value_rejects_symmetric_measurement_geometry` in
      `tests/test_autoresearch_stage_contract.py`.
- [x] 6.2 New unit test: first-entry materialized plan is byte-identical in effect to a correct
      hand-constructed plan using the same initial-sweep values. Added
      `test_materialized_initial_sweep_plan_matches_hand_constructed_candidates`.
- [x] 6.3 New unit test: "first entry" detection is correct given various `state["stage_history"]`
      contents. Added `test_is_stage_first_touch_reads_committed_stage_history_only` (empty,
      containing only other stages, containing a prior same-stage `in_progress` entry, and
      confirms B1/B2 are independent).
- [x] 6.4 New unit test: planning dispatch does not invoke the worker-launch code path on a stage's
      first entry, and does invoke it (with the narrowed prompt/contract) on a subsequent entry.
      Added `test_b1_first_touch_dispatch_never_renders_scientific_proposal_prompt_or_fetches_catalog`
      and `test_b1_subsequent_touch_dispatch_uses_narrowed_prompt_not_full_planning` in
      `tests/test_autoresearch_supervisor.py`, using a new `_advance_repo_v3_to_b1_width` session-
      surgery helper (since `initialize_session` only allows a new session to start at `A_CONTROL`).
- [x] 6.5 New unit test: a failed subsequent-entry planning attempt does not fall back to
      `state["stage_initial_sweeps"]` materialization. Added
      `test_b1_subsequent_touch_planning_failure_does_not_fall_back_to_initial_sweep` (spies on
      `_materialize_initial_sweep_plan`, asserts never called; confirms hard-stop with "repeated
      planning failure").
- [x] 6.6 New unit test: subsequent-entry `scientific_proposal` materializer produces a valid
      `execution_plan.json` for worker-chosen values both inside and outside the initial sweep's
      range. Added `test_materialize_scientific_proposal_plan_accepts_values_outside_initial_sweep`
      (values `[0.5, 60, 200]` against an initial sweep of `5..35`).
- [x] 6.7 Full targeted AutoResearch test suite (`tests/test_autoresearch_stage_contract.py`,
      `tests/test_autoresearch_supervisor.py`, `tests/test_autoresearch_worker_profiles.py`) passes
      after this change.
      106 passed (up from 97 baseline; +9 new tests), 0 failed.

## 7. Verification

- [ ] 7.1 Controlled HOST smoke on a strong worker profile through `A_CONTROL -> B1_WIDTH` (first
      entry, deterministic) `-> B1_WIDTH` (subsequent entry, narrowed worker contract), confirming the
      first-entry iteration produces no planning-worker invocation and the subsequent iteration's
      worker is genuinely free (chooses values outside or independent of the initial sweep).
      **Known risk:** the prior `A_CONTROL` HOST smoke (session
      `ema-anchor-a-control-smoke-20260904220007`) surfaced an unrelated interpretation-contract
      defect (`research_quality_assessment` "tradeoff comparison references an unknown candidate or
      region") that hard-stopped B1_WIDTH interpretation after 3 retries. If that defect is not fixed
      before this verification runs, this task may need to stop short of full interpretation
      completion (verify materialization/dispatch/execution only, mirroring how the dispatch-guard
      unit test stubs out execution) -- do not fold fixing that defect into this change's scope; note
      it as a blocker if hit again.
- [x] 7.2 Confirm `openspec validate --strict` passes for this change before archiving.
      `openspec validate --strict --changes autoresearch-b1-b2-scientific-proposal-v1` passed (6/6).
