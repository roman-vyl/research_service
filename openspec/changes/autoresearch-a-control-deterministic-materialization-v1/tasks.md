## 1. Pre-implementation checks

- [x] 1.1 Grep `scripts/autoresearch_supervisor.py` for every code path that assumes iteration 1 (or
      the `A_CONTROL` stage specifically) has a worker-authored `execution_plan.json` -- provenance
      fields, worker-identity logging, retry/attempt bookkeeping keyed on `planning_attempts`. Record
      findings; if any assume a non-null worker record for planning, note the required change here
      before writing code.
      Finding: `metadata["worker"]` (from `worker_identity`) records the session-level worker
      profile configured for the whole run, not "a worker process ran this iteration" -- set
      unconditionally regardless of whether planning launches a process. No code assumes a non-null
      per-iteration planning worker record. No change required.
- [x] 1.2 Confirm resume/recovery behavior for an iteration whose `execution_plan.json` already exists
      on disk (materialized, not worker-authored) matches existing resume semantics for a
      frozen/already-written plan -- no special-casing needed, or document why one is needed.
      Confirmed: resume reads `execution_plan.json` + `iteration_control.json` purely from disk
      shape/hash (`validate_execution_plan`, `control["plan_sha256"]`), with no field distinguishing
      worker-authored from materialized origin. No special-casing needed.

## 2. Deterministic materialization path

- [x] 2.1 Add a function that builds an `A_CONTROL` `execution_plan.json` payload from
      `reference_strategy()` and `validate_stage_context()`'s computed `stage_context`
      (`scripts/autoresearch_stage_contracts.py:308-317`, `:197-234`), with fixed
      `hypothesis`/`question`/`competing_explanation`/`market_property_proxy` strings describing the
      control measurement itself, `action: "batch"`, a single-candidate `canonical_request` matching
      the frozen strategy verbatim, and `hard_stop_reason: null`.
      Implemented as `_materialize_a_control_plan` in `scripts/autoresearch_supervisor.py`.
- [x] 2.2 Run the materialized payload through the unchanged `validate_stage_request`/
      `validate_stage_context` path before treating it as frozen -- same enforcement every
      worker-authored plan goes through today.
      Reuses `_freeze_plan`, which calls `validate_execution_plan` (which itself calls
      `validate_stage_request`/`validate_stage_context`) -- identical to the worker-authored path.
- [x] 2.3 Write the validated payload to the same `execution_plan.json` path every stage uses; no new
      artifact filename.
      Confirmed: no new filename introduced.

## 3. Supervisor dispatch

- [x] 3.1 Branch planning-stage dispatch on `active_stage == "A_CONTROL"` before any worker process is
      spawned: call the materialization path (2.1-2.3) instead of `render_planning_prompt` + worker
      launch.
      Implemented: dispatch guarded on `state.get("active_stage") == "A_CONTROL"` before the
      component-catalog fetch and before the worker-launch loop.
- [x] 3.2 Confirm the `A_CONTROL` iteration's interpretation call is unaffected -- fresh worker
      process, same prompt/schema as today, reads the materialized plan exactly as it would read a
      worker-authored one.
      Confirmed by inspection: the dispatch branch only guards the `planning_pending` control stage;
      interpretation dispatch code is untouched by this change.
- [x] 3.3 Confirm `planning_attempts` metadata bookkeeping (`supervisor_metadata.json`) reflects
      "materialized, no attempts" rather than recording a phantom zero-duration worker attempt.
      `metadata["planning_attempts"]` stays `[]`; a new `metadata["planning_materialized"] = True`
      marker records provenance instead.

## 4. Tests

- [x] 4.1 New unit test: materialized `A_CONTROL` plan is byte-identical in effect (same
      `canonical_request`, same `stage_context`) to a correct hand-constructed `A_CONTROL` plan already
      used as a fixture in `tests/test_autoresearch_stage_contract.py`.
      Added `test_materialized_a_control_plan_matches_hand_constructed_plan` and
      `test_materialize_a_control_plan_is_pure_function_of_state` in
      `tests/test_autoresearch_stage_contract.py`.
- [x] 4.2 New unit test: planning dispatch does not invoke the worker-launch code path when
      `active_stage == "A_CONTROL"` (mock/spy on the launch function, assert not called).
      Added `test_a_control_dispatch_never_renders_planning_prompt_or_launches_worker` in
      `tests/test_autoresearch_supervisor.py` (spies on `render_planning_prompt` and
      `_prepare_component_catalog_snapshot`, asserting neither is called; a real v3 session runs
      through `run_supervisor` up to freeze).
- [x] 4.3 Existing test: interpretation for `A_CONTROL` still runs as a fresh worker process and still
      requires the same semantic fields -- confirm no existing `tests/test_autoresearch_supervisor.py`
      coverage regresses.
      Confirmed: full existing suite still green (see 4.4); no interpretation-path test needed
      changes.
- [x] 4.4 Full targeted AutoResearch test suite (`tests/test_autoresearch_stage_contract.py`,
      `tests/test_autoresearch_supervisor.py`, `tests/test_autoresearch_worker_profiles.py`) passes
      after this change.
      97 passed (up from 94 baseline; +3 new tests), 0 failed.

## 5. Verification

- [x] 5.1 Controlled HOST smoke on a strong worker profile (e.g. `claude-sonnet46`) through
      `A_CONTROL -> B1_WIDTH` (or `B2_LOOKBACK`), confirming the `A_CONTROL` iteration produces no
      planning-worker invocation, interpretation still runs normally, and the session advances exactly
      as it does today from that point on.
      Ran session `ema-anchor-a-control-smoke-20260904220007`, worker `claude-sonnet46`,
      `--max-iterations 2`. Confirmed: iteration 1 (`A_CONTROL`) `execution_plan.json` was
      materialized with `planning_materialized: true` and zero `planning_attempts` -- no planning
      worker process launched; canonical execution and interpretation both ran and completed
      normally (327s interpretation). State advanced to `active_stage: B1_WIDTH`. Iteration 2's
      planning worker ran for real (293s), produced a genuine 9-candidate coarse sweep over
      `min_current_width_atr` (0.5..12.0 ATR) with fixed_parameters preserved verbatim from the
      stage contract, and canonical execution completed for all 9 candidates. The session
      ultimately hard-stopped on `repeated interpretation failure: 3 attempts` for iteration 2 --
      an existing `research_quality_assessment` "tradeoff comparison references an unknown
      candidate or region" validation defect in the interpretation contract, unrelated to this
      change's `A_CONTROL` materializer (which is scoped to planning, not interpretation, and
      is not touched by that failure). Confirms this change's scope (A_CONTROL requires no
      planning worker; every other stage/interpretation unaffected) end to end; the
      interpretation-contract defect is out of scope for this change and tracked separately.
- [x] 5.2 Confirm `openspec validate --strict` passes for this change before archiving.
      `openspec validate --strict --changes autoresearch-a-control-deterministic-materialization-v1`
      passed.
