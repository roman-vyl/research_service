## Context

See `proposal.md` - Why. Current planning dispatch (`scripts/autoresearch_supervisor.py`,
`render_planning_prompt`) is stage-agnostic: every iteration, every stage, gets a full-form planning
worker call that must hand-author `execution_plan.json` including `raw_spec`, `candidate_id`,
`experiment_id`, and `stage_context` fields the supervisor already computes independently for
post-hoc validation (`_stage_authority_context`, `expected_prerequisite_disposition_refs` in
`scripts/autoresearch_stage_contracts.py`). For `A_CONTROL`, `STAGE_DIMENSIONS` allows zero semantic
dimensions and `validate_stage_request` enforces exactly one candidate matching the frozen
`reference_strategy()` verbatim -- i.e. the correct plan for this stage is a pure function of session
state, with no worker-supplied content. This design covers only how the supervisor materializes that
one stage's plan deterministically and how planning dispatch skips the worker for it; it is Phase 1
of `docs/AUTORESEARCH_SCIENTIFIC_WORKER_INTERFACE_MASTER_PLAN.md`.

## Goals / Non-Goals

**Goals:**
- Supervisor materializes a valid `execution_plan.json` for `A_CONTROL` iterations without invoking
  a planning worker process.
- The materialized plan passes the same `validate_stage_request`/`validate_stage_context` checks a
  correct worker-authored plan would have passed -- no new, weaker validation path for this stage.
- Interpretation for `A_CONTROL` is unchanged: a fresh worker process still runs, still reports
  hypothesis/question/competing-explanation framing and a proposed next experiment.
- Recovery/resume: an `A_CONTROL` iteration whose plan was materialized (not worker-authored) resumes
  identically to today's resume paths for a frozen, already-written `execution_plan.json`.

**Non-Goals:**
- No scientific-proposal contract for `B1_WIDTH`/`B2_LOOKBACK` (master plan Phases 2-3).
- No materializer for mutable-dimension stages or any `values`/`range` scientific input.
- No B3 geometry design (master plan Phase 7).
- No change to `execution_plan.v2` schema shape, `batch_experiment_request.schema.json`, or worker
  profile resolution.
- No change to how any other stage's planning call is dispatched or prompted.

## Decisions

**Reuse existing stage-contract primitives for materialization instead of writing new construction
logic.** `reference_strategy()` (`scripts/autoresearch_stage_contracts.py:308-317`) already produces
the frozen naked strategy deep copy; `validate_stage_context()`
(`scripts/autoresearch_stage_contracts.py:197-234`) already computes the exact `stage_context` block
a correct plan must carry. The materialization path should call these same functions to build the
plan, then run the result through the unchanged `validate_stage_request()` path before it is treated
as frozen -- so the only new code is "build a plan object from these already-computed pieces and
`explanatory_metadata`/`hard_stop_reason: null`," not new derivation logic. Alternative considered:
write a separate, A_CONTROL-specific plan builder independent of the stage-contract module -- rejected
because it would duplicate the exact logic `_strip_allowed`/`validate_stage_request` already encode,
creating two sources of truth for what a valid `A_CONTROL` plan looks like.

**Planning dispatch branches on `active_stage == "A_CONTROL"` before worker launch, not inside the
worker-result handling path.** The skip must happen before any process is spawned (proposal's
`generic on result_path, not hardcoded filename` boundary-check property, confirmed during the master
plan's re-verification pass, is unaffected either way -- but not spawning a worker at all is simpler
to reason about for recovery than spawning-and-discarding). Alternative considered: still launch a
worker but with a trivial no-op prompt -- rejected, since it reintroduces exactly the
process-launch/timeout/retry surface this change exists to remove, for zero benefit.

**`hypothesis`/`question`/`competing_explanation` for the materialized `A_CONTROL` plan are fixed,
templated strings, not empty/null.** `execution_plan.v2.schema.json` requires these as non-empty
strings (`minLength: 1`); a materialized plan must still satisfy the schema. These fields describe
the control measurement itself ("measure the frozen naked strategy exactly once as comparison
baseline"), not a scientific choice -- the genuine scientific framing work shifts entirely to
interpretation of the control result, unchanged from today. Open question below covers exact wording
ownership.

**No new artifact filename introduced.** The materialized plan is still written to
`execution_plan.json` at the same path every other stage uses -- there is no `scientific_proposal.json`
in this change (that concept belongs to Phase 2+ and is explicitly out of scope). This avoids any
artifact-boundary allowlist change in this change.

## Risks / Trade-offs

- [Materializer produces a plan that technically passes schema but has degenerate/wrong content,
  undetected because no worker's independent judgment reviewed it before execution] → Mitigation: the
  materialized plan still passes through the unchanged `validate_stage_request`/`validate_stage_context`
  path before freeze; add a unit test asserting the materialized `A_CONTROL` plan is byte-identical in
  effect to what a correct full-form worker plan would have produced, using the same fixtures
  `tests/test_autoresearch_stage_contract.py` already exercises by hand.
- [Skipping the planning worker for `A_CONTROL` sets a precedent that gets silently generalized to
  other stages without the same "zero allowed dimensions" justification] → Mitigation: the spec delta
  names `A_CONTROL` explicitly, not "stages with a materializer"; any later stage skipping planning
  needs its own spec delta and its own justification.
- [Recovery/resume logic that currently assumes iteration 1's `execution_plan.json` came from a
  worker process (e.g. for provenance/logging) breaks on a materialized plan] → Mitigation: this must
  be verified against actual resume-path code during implementation (task item), not assumed here;
  flagged as an implementation-time check, not a design gap, since the plan's on-disk shape does not
  change, only its authorship.

## Migration Plan

Additive, single-stage, no schema version bump: `execution_plan.json`'s shape for `A_CONTROL` is
unchanged (still `bbb_autoresearch_execution_plan.v2`), only its authorship moves from worker to
supervisor. No existing session's stored `A_CONTROL` iteration needs migration -- old sessions already
have a worker-authored plan on disk and are read unchanged. Rollback is deleting the dispatch branch;
no data format reverts needed.

## Open Questions

- Exact wording/ownership of the templated `hypothesis`/`question`/`competing_explanation` strings for
  the materialized `A_CONTROL` plan -- supervisor-hardcoded constant vs. derived from `program.md`/
  `SKILL.md` text at materialization time. Does not change the spec, the chosen approach, or the task
  breakdown; resolve during implementation.
- Whether resume/recovery code paths have any existing assumption that iteration 1's plan is
  worker-authored (e.g. worker-identity/provenance fields expecting a non-null worker record) --
  needs a targeted code check as an early implementation task, not a design decision.
