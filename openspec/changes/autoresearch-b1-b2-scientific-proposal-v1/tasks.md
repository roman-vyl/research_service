## 1. Pre-implementation checks

- [ ] 1.1 Confirm the exact shape and append-conditions of `state["stage_history"]` in
      `scripts/autoresearch_supervisor.py` (`_advance_state`) -- verify it is appended for every
      committed v3 iteration regardless of disposition status (including `in_progress`), and confirm
      no code path currently reads it for anything this change would conflict with.
- [x] 1.2 Confirm `_STATE_V3_KEYS` exact-keyset validation in `scripts/autoresearch_supervisor.py`.
      Confirmed: `validate_state` (`:957-968`) calls `_require_exact_keys(state, _STATE_V3_KEYS, ...)`
      -- a strict, not minimum, set match. `stage_initial_sweeps` is added as a **required** key;
      historical session-state compatibility is an explicit non-goal (design.md), so no `.get()`
      fallback, dual-read, or state contract version bump is introduced. A pre-existing v3 session
      missing the key is expected to fail `validate_state` and is not made loadable again.
- [ ] 1.3 Confirm whether the bound component for `B1_WIDTH`/`B2_LOOKBACK` can ever already be present
      in a later iteration's "reference" (verify against actual `reference_strategy()` semantics --
      does every B1/B2 iteration start from the same frozen naked strategy, or can prior iterations'
      committed choices persist into a later iteration's baseline?). This determines whether the
      component-insertion function needs a real "component present, overwrite" branch or only ever
      exercises "component absent, insert".
- [ ] 1.4 Locate the current exact line number of the output-boundary check in
      `scripts/autoresearch_supervisor.py` (previously ~line 862, may have shifted) and confirm it
      remains generic on `result_path` (filename-agnostic), consistent with the `A_CONTROL` change's
      finding, before deciding whether a new `scientific_proposal.json`-shaped artifact needs an
      explicit allowlist entry or is already covered generically.
- [ ] 1.5 Grep for any existing code or test that assumes every `B1_WIDTH`/`B2_LOOKBACK` iteration is
      worker-authored (mirroring task 1.1 from the archived `A_CONTROL` change) -- provenance
      fields, worker-identity logging, retry/attempt bookkeeping. Record findings.

## 2. `stage_initial_sweeps` state field

- [ ] 2.1 Add `stage_initial_sweeps` as a new top-level v3 state key, sourced from the session init
      template (mirroring the existing `research_quality_policy` template -> state precedent in
      `scripts/autoresearch_init.py`). Shape: `{"B1_WIDTH": {"values": [...]}, "B2_LOOKBACK": {"values": [...]}}`
      only -- no other keys.
- [ ] 2.2 Add `stage_initial_sweeps` to `autoresearch/templates/ema_anchor_stage_contract_session.json`
      (and any other v3 session template). **Do not choose the actual numeric `values` here without
      an explicit operator decision.**
- [ ] 2.3 Add `"stage_initial_sweeps"` to `_STATE_V3_KEYS` in `scripts/autoresearch_supervisor.py`.
      No `.get()` fallback, no dual-read, no state contract version bump -- a pre-existing v3 session
      missing the key is expected to fail `validate_state` (per 1.2 finding); this is intentional.

## 3. Deterministic first-entry materialization

- [ ] 3.1 Add a component-insertion function (the missing inverse of `_strip_allowed`) in
      `scripts/autoresearch_stage_contracts.py`, building `{**fixed_parameters, parameter_name: value}`
      (nested `params_storage` under `"params"`, flat at top level, mirroring `_strip_allowed`'s
      `expected_fixed` construction at `:357-368`) and inserting it into `raw_spec["setups"]` when
      absent, or replacing the existing bound instance's fields when present (per 1.3's finding).
- [ ] 3.2 Add a function that detects "first entry into stage X" from `state["stage_history"]`
      (`not any(e["stage"] == X for e in state["stage_history"])`).
- [ ] 3.3 Add a function that materializes a `B1_WIDTH`/`B2_LOOKBACK` first-entry `execution_plan.json`
      from `state["stage_initial_sweeps"][stage]["values"]`, the frozen `semantic_binding` for that
      stage's dimension, and the component-insertion function (3.1) -- one candidate per initial-sweep
      value, deterministic `candidate_id`/`experiment_id` generation (e.g.
      `"{stage-slug}-initial-sweep"` / `"{stage-slug}-{value}"`, namespaced by the existing
      `_with_canonical_experiment_id`/`_session_scoped_experiment_id` path unchanged).
- [ ] 3.4 Run the materialized first-entry payload through the unchanged `validate_stage_request`/
      `validate_stage_context` path before treating it as frozen.

## 4. Narrowed scientific_proposal for subsequent entries

- [ ] 4.1 Define the exact `scientific_proposal` artifact contract for a subsequent B1/B2 iteration
      (field list per `proposal.md`'s conceptual shape: `hypothesis`, `question`, `values`,
      `rationale`, `expected_information_gain`) -- finalize `contract_version` naming and artifact
      filename.
- [ ] 4.2 If the artifact filename is new (not `execution_plan.json`), add it to the output-boundary
      protected/allowed filename set at the location confirmed in 1.4.
- [ ] 4.3 Add a materializer that consumes the `scientific_proposal` and produces an
      `execution_plan.json` using the same component-insertion function (3.1), frozen
      `semantic_binding`, and candidate/experiment id generation as the first-entry path -- one shared
      implementation, two call sites (first-entry values vs worker-chosen values).
- [ ] 4.4 Write a narrowed planning prompt (new prompt file or conditional section in
      `autoresearch/prompts/planning.md`) for subsequent B1/B2 iterations: drop
      `batch_request_schema_path`/full component-catalog reading and `stage_context` verbatim
      copy-paste; keep program/skill/state/journal reading, coarse-to-fine / boundary-resolution /
      information-dense-batch guidance, and `analysis_dir`.
- [ ] 4.5 Run every subsequent-entry materialized candidate through the unchanged
      `validate_stage_request`/`validate_stage_context` path before treating it as frozen.

## 5. Supervisor dispatch

- [ ] 5.1 Branch planning-stage dispatch for `active_stage in {"B1_WIDTH", "B2_LOOKBACK"}` on the
      first-entry detection (3.2): first entry -> deterministic materialization (3.3-3.5), no worker
      process; subsequent entry -> narrowed worker contract (4.1-4.5).
- [ ] 5.2 Confirm interpretation for both first-entry and subsequent-entry B1/B2 iterations is
      unaffected -- fresh worker process, same prompt/schema as today.
- [ ] 5.3 Confirm `planning_attempts` metadata bookkeeping reflects "materialized, no attempts" for
      first-entry iterations (mirroring `A_CONTROL`'s `planning_materialized` marker) and normal
      attempt bookkeeping for subsequent-entry iterations.
- [ ] 5.4 Confirm no fallback to `stage_initial_sweeps` occurs once a stage has one committed entry,
      including when a subsequent planning attempt fails and retries (per the hard acceptance
      criterion in `proposal.md`).

## 6. Tests

- [ ] 6.1 New unit test: component-insertion function produces the expected `raw_spec` for both the
      component-absent and component-present cases, for both `B1_WIDTH` and `B2_LOOKBACK`.
- [ ] 6.2 New unit test: first-entry materialized plan is byte-identical in effect to a correct
      hand-constructed plan using the same initial-sweep values, mirroring
      `test_materialized_a_control_plan_matches_hand_constructed_plan`.
- [ ] 6.3 New unit test: "first entry" detection is correct given various `state["stage_history"]`
      contents (empty, containing only other stages, containing a prior entry for the same stage with
      `in_progress` status).
- [ ] 6.4 New unit test: planning dispatch does not invoke the worker-launch code path on a stage's
      first entry (mirroring `test_a_control_dispatch_never_renders_planning_prompt_or_launches_worker`),
      and does invoke it (with the narrowed prompt/contract) on a subsequent entry.
- [ ] 6.5 New unit test: a failed subsequent-entry planning attempt does not fall back to
      `state["stage_initial_sweeps"]` materialization.
- [ ] 6.6 New unit test: subsequent-entry `scientific_proposal` materializer produces a valid
      `execution_plan.json` for worker-chosen values both inside and outside the initial sweep's
      range.
- [ ] 6.7 Full targeted AutoResearch test suite (`tests/test_autoresearch_stage_contract.py`,
      `tests/test_autoresearch_supervisor.py`, `tests/test_autoresearch_worker_profiles.py`) passes
      after this change.

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
- [ ] 7.2 Confirm `openspec validate --strict` passes for this change before archiving.
