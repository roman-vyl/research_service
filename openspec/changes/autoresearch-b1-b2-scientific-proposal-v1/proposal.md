## Why

`autoresearch-a-control-deterministic-materialization-v1` (archived) established the precedent: when
a stage's `execution_plan.json` content is mechanically derivable from frozen session/stage-contract
state, the harness should materialize it directly instead of requiring a worker to hand-author it.
`B1_WIDTH` and `B2_LOOKBACK` are the next step in that same direction, but they differ from
`A_CONTROL` in one essential way: each has exactly one genuine scientific degree of freedom (the
candidate values for its bound mutable parameter -- `min_current_width_atr` for B1,
`lookback` for B2), which must remain worker-owned. Everything else the worker currently must
hand-author in a full `execution_plan.json` -- `component_id`, `instance_id`, `parameter_name`,
`fixed_parameters`, the full `raw_spec`, `candidate_id`, `experiment_id`, `stage_context` -- is
mechanically derivable today from the frozen `stage_contract.semantic_bindings`
(`scripts/autoresearch_stage_contracts.py:35-40` `STAGE_DIMENSIONS`, per-dimension binding structure
in `autoresearch/templates/ema_anchor_stage_contract_session.json`) plus `reference_strategy()`
(`scripts/autoresearch_stage_contracts.py:308-317`).

A live controlled HOST smoke run during this session's `A_CONTROL` verification (session
`ema-anchor-a-control-smoke-20260904220007`) showed a capable worker (`claude-sonnet46`) still
spending ~293s of planning-call latency to hand-author a full `B1_WIDTH` batch, and separately
demonstrated that this same worker can derive a sensible 9-point coarse sweep unprompted (0.5 to
12.0 ATR) -- confirming the scientific-values choice is real worker content worth keeping, while the
surrounding `raw_spec`/schema mechanics remain pure overhead identical in kind to what `A_CONTROL`
already removed.

This change goes one step further than a pure schema narrowing: it also removes the planning LLM
call entirely for each stage's **first** entry, using an init-time-supplied deterministic starting
grid (`stage_initial_sweeps`) -- a standardized first observation of the response curve, not a
scientific decision, so there is nothing for a worker to contribute on that one iteration. Every
subsequent entry into that same stage restores full worker freedom: the worker may choose any values,
extend beyond the initial grid in either direction, densify a region, or test a boundary -- the
initial sweep has no further authority over the investigation once one iteration of that stage has
committed.

## What Changes

- New session-state sibling field `stage_initial_sweeps`, sourced from the session init template
  (same pattern already used for `research_quality_policy`) and copied into frozen v3 state at init.
  Deliberately narrow shape -- per stage, only a `values` list:
  ```json
  "stage_initial_sweeps": {
    "B1_WIDTH": {"values": [...]},
    "B2_LOOKBACK": {"values": [...]}
  }
  ```
  No `min`/`max`/`step`/`domain`/`recommended_range`/`boundary_policy`/`refinement_policy` fields --
  this is a one-time starting grid, never a scientific-boundary or optimizer-policy contract. It lives
  as a state sibling field, **not** inside `stage_contract`: `stage_contract`'s strict `_exact()`
  keyset validation (`scripts/autoresearch_stage_contracts.py:101-177`) and
  `autoresearch_init.py`'s cross-validation of `fixed_parameters` against the live component catalog
  (`autoresearch_init.py:118-131`) both treat that structure as catalog-derived binding identity, not
  worker-facing starting values -- entangling the two would conflict with both checks and with the
  conceptual boundary "semantic binding says what the dimension means and how it materializes;
  initial sweep says what standard first observation begins the investigation."
- Deterministic materialization, mirroring `_materialize_a_control_plan`'s existing pattern, for a
  stage's first entry only. "First entry" is detected from the already-existing
  `state["stage_history"]` list (appended by `_advance_state`,
  `scripts/autoresearch_supervisor.py` around `_advance_state`'s stage-history update): a stage has no
  prior entry there until one of its iterations has actually committed. A batch that fails before
  commit does not count -- a retry is still treated as first entry and re-materializes the same
  deterministic starting grid; there is no LLM involvement and nothing to retry differently. On the
  first committed iteration for a stage, `stage_initial_sweeps` permanently loses authority for that
  stage in that session: there is no fallback to it, ever, including when a later planning call fails
  -- a failed subsequent planning call retries planning, never silently substitutes the initial sweep.
- New deterministic materializer logic that can insert a stage's bound component into the naked
  reference strategy when absent (the documented case at
  `scripts/autoresearch_stage_contracts.py:293-296`: "B1/B2 targets are explicit prototypes that may
  be absent from the naked strategy"). No such insertion logic exists anywhere in the codebase today
  -- `_strip_allowed()` (`scripts/autoresearch_stage_contracts.py:320-401`) only strips a *present*
  bound component down to `<mutable>` for comparison; it has no inverse. This same insertion logic is
  reused for every subsequent worker-chosen candidate as well, not only the first-entry deterministic
  batch.
- A new, narrower `scientific_proposal` worker-facing contract for a stage's *subsequent* (non-first)
  planning iterations only. The worker supplies scientific content (hypothesis, question, candidate
  values, rationale, expected information gain); the harness materializes `component_id`,
  `instance_id`, `parameter_name`, `fixed_parameters`, the full `raw_spec`, `candidate_id`,
  `experiment_id`, and `stage_context` from the frozen `semantic_binding` -- the same WHAT/HOW split
  already established for `A_CONTROL`. No scientific-proposal artifact exists for a stage's first
  (deterministic) entry -- inventing one purely for artifact uniformity was explicitly rejected;
  `execution_plan.json` for that iteration honestly reflects a materialized, not worker-authored,
  experiment. Component catalog delivery to the worker is unnecessary for these locked stages (the
  binding is already frozen) and is dropped from the narrowed planning contract; it remains relevant
  only for future exploratory stages, out of scope here.
- **BREAKING** (normative, not implementation): `bbb-autoresearch-v1`'s "Fresh worker per iteration"
  requirement -- already carrying the `A_CONTROL` exception from the prior change -- gains a second,
  separate exception scoped to `B1_WIDTH`/`B2_LOOKBACK`'s first-entry case: the supervisor
  deterministically materializes that one iteration's plan from `stage_initial_sweeps` instead of
  launching a planning worker process; every subsequent iteration of that stage, and every
  interpretation call, continues to run as a fresh worker process unchanged.
- Existing `validate_stage_request()`/`validate_stage_context()`/`_strip_allowed()`
  (`scripts/autoresearch_stage_contracts.py:404-423`, `:197-234`, `:320-401`) remain the unchanged,
  independent post-hoc defense for every candidate produced by the materializer -- first-entry and
  subsequent alike. No weakening of this validation path.
- If a new `scientific_proposal.json`-shaped artifact type is introduced for non-first iterations, it
  must be added to the output-boundary protected/allowed filename set at the boundary check in
  `scripts/autoresearch_supervisor.py` (the same check that already fail-closed on an unexpected
  output filename during the original `qwen35-local` smoke) -- exact mechanism is a design.md
  decision.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `bbb-autoresearch-v1`: the "Fresh worker per iteration" requirement gains a second explicit
  exception, scoped to `B1_WIDTH`/`B2_LOOKBACK`'s first entry into each stage: the supervisor
  deterministically materializes that one iteration's `execution_plan.json` from
  `state["stage_initial_sweeps"]` and the frozen `stage_contract` instead of launching a planning
  worker process. Every subsequent iteration of that stage, and every interpretation call for every
  stage, continues to run as a fresh worker process per this requirement unchanged.

## Impact

- `scripts/autoresearch_supervisor.py`: planning-stage dispatch gains a second stage-aware branch
  (alongside the existing `A_CONTROL` one) that checks `state["stage_history"]` for a prior committed
  entry at the active stage before deciding whether to materialize deterministically or invoke the
  (narrowed) planning worker -- implementation detail for design.md, not decided here.
- `scripts/autoresearch_init.py`: gains reading of an `stage_initial_sweeps`-shaped field from the
  session template into frozen v3 state, following the existing `research_quality_policy` precedent.
- `scripts/autoresearch_stage_contracts.py`: new component-insertion logic (the missing inverse of
  `_strip_allowed()`), reused by both the first-entry materializer and the narrowed
  `scientific_proposal` materializer for subsequent iterations.
- `autoresearch/templates/ema_anchor_stage_contract_session.json` (and any other v3 session template):
  gains the `stage_initial_sweeps` field. **Exact numeric values are an explicit open operator
  decision, not proposed here** -- this proposal defines the field's narrow shape and materialization
  semantics only; the operator supplies the actual starting grid per programme/session.
- `autoresearch/prompts/planning.md`: needs a narrowed variant (or conditional section) for
  `B1_WIDTH`/`B2_LOOKBACK` subsequent-iteration planning that no longer requires reading/matching
  `batch_experiment_request.schema.json`'s full shape or the full `component_catalog.json` snapshot --
  exact prompt content is a design.md decision. `A_CONTROL`'s already-removed planning call and every
  other stage's full-form planning contract are unaffected.
- `openspec/specs/bbb-autoresearch-v1/spec.md`: second delta to "Fresh worker per iteration",
  additive to the `A_CONTROL` exception already synced there.
- `docs/AUTORESEARCH_SCIENTIFIC_WORKER_INTERFACE_MASTER_PLAN.md`: this change implements master-plan
  Phases 2-3 (B1/B2 scientific proposal + materializer), refined with the initial-sweep mechanism
  agreed during this session's design review (the master plan's original conceptual B1/B2 proposal
  shape did not yet include the deterministic-first-entry concept).
- Existing regression safety net (`tests/test_autoresearch_stage_contract.py`,
  `tests/test_autoresearch_supervisor.py`) is expected to gain new coverage mirroring the `A_CONTROL`
  precedent (materializer-equivalence tests, dispatch-guard tests, plus new coverage for the
  component-insertion logic and the first-entry/subsequent-entry branch), but is not modified by this
  proposal itself.
- Explicitly out of scope: `B3_WIDTH_X_LOOKBACK` geometry design, `C_ENTRY_REGION_SELECTION`/
  `D_EXIT_GEOMETRY` (provisional stages), interpretation contract redesign (including the unrelated
  `research_quality_assessment` "tradeoff comparison references an unknown candidate or region"
  defect surfaced during the `A_CONTROL` HOST smoke -- tracked separately, not folded in here),
  evidence plots/renderer, worker profile changes, and Research Service/Strategy Engine/Market Data
  Service production contracts. `A`→`B`/`B`→`B3` stage transition semantics are unchanged; only what
  happens *inside* `B1_WIDTH`/`B2_LOOKBACK` planning dispatch is in scope.
- Canonical for all worker profiles (`claude-sonnet46`, `codex-gpt56-sol`, `glm52-opencode`,
  `qwen35-local`) -- not a per-profile branch, mirroring the same principle established for the
  `A_CONTROL` change.
- No production Research Service / Strategy Engine / Market Data Service change.
