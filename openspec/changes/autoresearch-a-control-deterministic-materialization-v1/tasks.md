## 1. Pre-implementation checks

- [ ] 1.1 Grep `scripts/autoresearch_supervisor.py` for every code path that assumes iteration 1 (or
      the `A_CONTROL` stage specifically) has a worker-authored `execution_plan.json` -- provenance
      fields, worker-identity logging, retry/attempt bookkeeping keyed on `planning_attempts`. Record
      findings; if any assume a non-null worker record for planning, note the required change here
      before writing code.
- [ ] 1.2 Confirm resume/recovery behavior for an iteration whose `execution_plan.json` already exists
      on disk (materialized, not worker-authored) matches existing resume semantics for a
      frozen/already-written plan -- no special-casing needed, or document why one is needed.

## 2. Deterministic materialization path

- [ ] 2.1 Add a function that builds an `A_CONTROL` `execution_plan.json` payload from
      `reference_strategy()` and `validate_stage_context()`'s computed `stage_context`
      (`scripts/autoresearch_stage_contracts.py:308-317`, `:197-234`), with fixed
      `hypothesis`/`question`/`competing_explanation`/`market_property_proxy` strings describing the
      control measurement itself, `action: "batch"`, a single-candidate `canonical_request` matching
      the frozen strategy verbatim, and `hard_stop_reason: null`.
- [ ] 2.2 Run the materialized payload through the unchanged `validate_stage_request`/
      `validate_stage_context` path before treating it as frozen -- same enforcement every
      worker-authored plan goes through today.
- [ ] 2.3 Write the validated payload to the same `execution_plan.json` path every stage uses; no new
      artifact filename.

## 3. Supervisor dispatch

- [ ] 3.1 Branch planning-stage dispatch on `active_stage == "A_CONTROL"` before any worker process is
      spawned: call the materialization path (2.1-2.3) instead of `render_planning_prompt` + worker
      launch.
- [ ] 3.2 Confirm the `A_CONTROL` iteration's interpretation call is unaffected -- fresh worker
      process, same prompt/schema as today, reads the materialized plan exactly as it would read a
      worker-authored one.
- [ ] 3.3 Confirm `planning_attempts` metadata bookkeeping (`supervisor_metadata.json`) reflects
      "materialized, no attempts" rather than recording a phantom zero-duration worker attempt.

## 4. Tests

- [ ] 4.1 New unit test: materialized `A_CONTROL` plan is byte-identical in effect (same
      `canonical_request`, same `stage_context`) to a correct hand-constructed `A_CONTROL` plan already
      used as a fixture in `tests/test_autoresearch_stage_contract.py`.
- [ ] 4.2 New unit test: planning dispatch does not invoke the worker-launch code path when
      `active_stage == "A_CONTROL"` (mock/spy on the launch function, assert not called).
- [ ] 4.3 Existing test: interpretation for `A_CONTROL` still runs as a fresh worker process and still
      requires the same semantic fields -- confirm no existing `tests/test_autoresearch_supervisor.py`
      coverage regresses.
- [ ] 4.4 Full targeted AutoResearch test suite (`tests/test_autoresearch_stage_contract.py`,
      `tests/test_autoresearch_supervisor.py`, `tests/test_autoresearch_worker_profiles.py`) passes
      after this change.

## 5. Verification

- [ ] 5.1 Controlled HOST smoke on a strong worker profile (e.g. `claude-sonnet46`) through
      `A_CONTROL -> B1_WIDTH` (or `B2_LOOKBACK`), confirming the `A_CONTROL` iteration produces no
      planning-worker invocation, interpretation still runs normally, and the session advances exactly
      as it does today from that point on.
- [ ] 5.2 Confirm `openspec validate --strict` passes for this change before archiving.
