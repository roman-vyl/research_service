## Context

See `proposal.md` - Why. `A_CONTROL`'s materializer (`_materialize_a_control_plan`,
`scripts/autoresearch_supervisor.py`) established the WHAT/HOW split for a stage with zero worker
content. `B1_WIDTH`/`B2_LOOKBACK` each have exactly one genuine scientific degree of freedom
(candidate values for the bound dimension). This design covers two independent mechanisms that
together remove the mechanical-materialization burden while preserving that one degree of freedom in
full:

1. A deterministic **first-entry** materialization (no worker at all) driven by an init-supplied
   starting grid.
2. A narrowed **scientific_proposal** worker contract for every subsequent entry into that stage.

This is master-plan Phases 2-3, refined during this session's design review to add the first-entry
mechanism (not present in the master plan's original conceptual shape).

## Goals / Non-Goals

**Goals:**
- A stage's first committed touch (per `state["stage_history"]`) is fully deterministic: no planning
  worker process, `execution_plan.json` built directly from `state["stage_initial_sweeps"][stage]`
  and the frozen `semantic_binding` for that dimension.
- Every subsequent touch of that stage restores full worker freedom over candidate values via a
  narrowed `scientific_proposal` contract; the initial sweep has zero effect on this decision and is
  never referenced by it.
- New component-insertion logic (naked strategy lacks the bound component) is shared by both the
  first-entry materializer and the subsequent-entry materializer -- one implementation, not two.
- Every produced candidate, first-entry or subsequent, passes the unchanged
  `validate_stage_request()`/`validate_stage_context()`/`_strip_allowed()` path before freeze.
- `stage_initial_sweeps` has a deliberately narrow shape (`{stage: {"values": [...]}}`) with no
  domain/boundary/policy semantics, and lives outside `stage_contract`.

**Non-Goals:**
- Backward compatibility of session state initialized before this change. AutoResearch session state
  is execution-local orchestration state, not a durable cross-version storage contract; a pre-existing
  session missing `stage_initial_sweeps` is expected to fail `validate_state`'s exact-keyset check
  and is not made loadable again -- no dual-read, no `.get()` fallback, no on-disk migration, no new
  state contract version (see Migration Plan).
- Choosing actual numeric values for `stage_initial_sweeps` -- open operator decision (see below).
- `B3_WIDTH_X_LOOKBACK` geometry design (master plan Phase 7).
- Merging planning and interpretation into one call (master plan Phase 9, separate open question).
- Any change to `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` (provisional, unaffected).
- Component-catalog delivery redesign for future exploratory stages -- only removing it from the
  narrowed B1/B2 subsequent-entry prompt, since binding is already frozen for these locked stages.
- Fixing the unrelated interpretation-contract `research_quality_assessment` defect found during the
  `A_CONTROL` HOST smoke.

## Decisions

**`stage_initial_sweeps` lives as a state sibling field, sourced from the session template, not
inside `stage_contract`.** Two independent existing checks would conflict if it were folded into
`stage_contract`: `validate_stage_contract()`'s `_exact()` calls (`scripts/autoresearch_stage_contracts.py:101-177`)
enumerate a fixed keyset per binding target, and `autoresearch_init.py:118-131`'s
`_load_v3_stage_contract` cross-validates `fixed_parameters` against the live component catalog --
logic that has no meaning for a sweep-values list and must not be asked to validate one. Modeling
`stage_initial_sweeps` as a new top-level state key (alongside `stage_history`, which already exists
in `_STATE_V3_KEYS`) is a same-class additive change to the state schema, with no hash/identity
coupling to `stage_contract`. Alternative considered: a separate `autoresearch/programme/search_domains.json`-style
file -- rejected as an unnecessary second source of truth for something that is genuinely
session-scoped (an operator may reasonably want different starting grids for different sessions of
the same programme), and the `research_quality_policy` precedent (template → frozen v3 state) already
covers exactly this shape of decision.

**"First entry" is detected from `state["stage_history"]`, not a new counter or flag.**
`_advance_state` (`scripts/autoresearch_supervisor.py`, stage-history update near its `next_stage`
computation) already appends `{"iteration_id", "stage", "status"}` for every committed v3 iteration,
regardless of disposition status (`in_progress` included). "First entry into stage X" is exactly
`not any(e["stage"] == X for e in state["stage_history"])`, evaluated from state as loaded at the
start of planning dispatch for the current iteration -- which by construction reflects only prior
*committed* iterations, never the in-flight one. This gives the required "retry after uncommitted
failure is still first" property for free: if a first-touch batch fails before its iteration commits,
the supervisor's next attempt at the same iteration reads the same `stage_history` (still lacking an
entry for that stage) and re-materializes deterministically again, with no new state or retry-counter
logic needed. Alternative considered: a dedicated `first_touch_done` flag per stage -- rejected as
redundant, since `stage_history` already answers the question exactly and keeping a second signal in
sync would only add a desynchronization risk.

**No fallback to `stage_initial_sweeps` after a stage's first commit, under any failure condition.**
Once `state["stage_history"]` contains an entry for a stage, dispatch for that stage unconditionally
takes the worker-planning path (narrowed `scientific_proposal` contract) -- there is no code path that
re-checks `stage_initial_sweeps` at that point. A failed subsequent planning attempt retries planning
exactly as today's full-form retry loop already does (bounded by `max_consecutive_agent_failures`);
it does not fall through to deterministic materialization. This is a hard acceptance criterion from
the user: `stage_initial_sweeps` must never become a hidden fallback policy that silently
re-substitutes a canned experiment when the scientific process stalls.

**Component insertion mirrors `_strip_allowed`'s existing fixed-field construction, in the reverse
direction.** For a bound dimension whose component is absent from the reference strategy (the
documented case at `scripts/autoresearch_stage_contracts.py:293-296`), the materializer builds
`{**fixed_parameters, parameter_name: <value>}` -- nested `params_storage` under the component's
`"params"` key, flat `params_storage` at the top level of the component dict, exactly mirroring the
`expected_fixed` construction `_strip_allowed` already builds for the *strip* direction
(`scripts/autoresearch_stage_contracts.py:357-368`) -- and appends the resulting component object into
`raw_spec["setups"]`. If the component is already present (verified during implementation whether
this occurs structurally for these two stages, given each starts from the same frozen naked
reference every iteration), the same `{**fixed_parameters, parameter_name: <value>}` object replaces
the existing instance's mutable field via the same path, never partially merging stray keys. This one
function serves both the first-entry deterministic materializer and the subsequent-entry
`scientific_proposal` materializer -- a single implementation, exercised by both call sites.

**No scientific_proposal artifact for a stage's first entry.** The first iteration has no worker
content to record -- `execution_plan.json` for it is materializer-authored end to end, exactly like
`A_CONTROL`'s. If a lightweight origin tag is useful downstream (`"initial_sweep"` vs
`"scientific_proposal"`), it belongs in `explanatory_metadata`, mirroring the
`{"materialized_by": "supervisor", "worker": None}` shape `_materialize_a_control_plan` already
writes there -- exact key names are an implementation-time choice, not specified further here to
avoid over-designing a provenance contract nobody has asked to consume yet.

**Candidate/experiment identity for the first-entry materialized batch.** There is no worker to
supply even a short logical id for this one iteration. The materializer generates a deterministic
logical `experiment_id` (e.g. derived from the stage name, such as `"b1-width-initial-sweep"`) and
per-value `candidate_id`s (e.g. `"b1-width-{value}"`, matching the human-readable style
`claude-sonnet46` itself chose unprompted during the HOST smoke,
`b1-width-0.5atr`/`b1-width-1.0atr`/...) -- both still pass through the existing
`_with_canonical_experiment_id`/`_session_scoped_experiment_id` namespacing
(`scripts/autoresearch_supervisor.py` around `_session_scoped_experiment_id`) unchanged. Exact string
template is an implementation detail, not a normative contract.

**Narrowed planning contract for subsequent B1/B2 iterations.** Dropped relative to today's full
`planning.md`: the instruction to read and exactly match `batch_experiment_request.schema.json`'s
full shape, the full `component_catalog.json` snapshot (unnecessary once binding is frozen for a
locked stage), and verbatim `stage_context` copy-paste (replaced with a compact stage-authority
statement: "you may vary only `<parameter_name>`; everything else is fixed"). Retained: reading
`program.md`/`skill.md`/`state`/journal tail, the coarse-to-fine / boundary-resolution /
information-dense-batch guidance language (unchanged scientific-process guidance), and `analysis_dir`
for textual analysis output. Exact prompt text is an implementation task, not fully specified here.

## Risks / Trade-offs

- [`stage_initial_sweeps` numeric values, once chosen by an operator, get silently treated as a de
  facto scientific boundary by future maintainers or by a weaker worker that over-anchors on them
  despite full freedom] → Mitigation: the narrowed subsequent-entry `scientific_proposal` contract
  and its prompt must not reference the initial sweep at all; nothing in the worker-facing surface for
  iteration 2+ exposes what the initial values were, so there is nothing to anchor on beyond whatever
  the worker itself reads from prior evidence/journal (which is the intended signal).
- [Component-insertion logic has a bug that silently produces a structurally-invalid but
  schema-passing candidate] → Mitigation: unchanged, independent `validate_stage_request`/
  `_strip_allowed` path is the last-line defense for every candidate, first-entry and subsequent
  alike -- same mitigation pattern as `A_CONTROL`.
- [A session initialized before this change lacks `stage_initial_sweeps` in its frozen state] →
  Not mitigated, by design: AutoResearch session state is execution-local orchestration state, not a
  durable cross-version storage contract. `stage_initial_sweeps` is added as a required key in
  `_STATE_V3_KEYS`; `validate_state`'s exact-keyset check (`scripts/autoresearch_supervisor.py:957-968`)
  fail-closes on any session state that predates this change. This is intentional, not a gap -- see
  Migration Plan.
- [New component-insertion code, exercised for the first time by this change, has broader blast
  radius than `A_CONTROL`'s materializer since it also runs on every worker-authored subsequent
  candidate, not just a single deterministic one] → Mitigation: unit tests must cover both the
  component-absent and component-present insertion paths independently, mirroring
  `test_b1_allows_only_width_and_preserves_frozen_control_exit` and similar existing fixtures in
  `tests/test_autoresearch_stage_contract.py`.

## Migration Plan

**Historical session-state compatibility is a non-goal.** AutoResearch session state
(`state.json`) is execution-local orchestration state for one running research session, not a
durable cross-version storage contract -- there is no requirement that a session initialized under
one internal contract shape remain loadable after the contract changes. `stage_initial_sweeps` is
added as a **required** key in `_STATE_V3_KEYS` (`scripts/autoresearch_supervisor.py:194-201`); the
contract version stays `bbb_autoresearch_state.v3` (in-place internal contract change, not a version
bump), and `validate_state`'s existing exact-keyset check
(`scripts/autoresearch_supervisor.py:957-968`) fail-closes on any state predating this change --
correctly, by design. No dual-read path, no `.get()`-with-default fallback, no on-disk migration
script, and no new `bbb_autoresearch_state.v4` contract version are introduced for this. A
pre-existing session that predates this change simply cannot resume past this point; that is an
accepted, intentional consequence, not a defect to engineer around.

`scripts/autoresearch_init.py` and every v3 session template are updated so every session
initialized *after* this change always carries `stage_initial_sweeps`. No change to
`execution_plan.v2`'s schema shape or `contract_version` -- both the first-entry materialized plan and
subsequent worker-authored plans continue to produce the same `bbb_autoresearch_execution_plan.v2`
shape; only authorship and (for subsequent entries) the worker-facing input contract change. If a new
`scientific_proposal.json` artifact type is introduced, it must be added to the output-boundary
protected/allowed filename set (`scripts/autoresearch_supervisor.py`'s boundary check) before any
worker can write one -- an implementation task, verified by a dedicated boundary test mirroring the
`A_CONTROL` precedent's coverage. Rollback is reverting the dispatch branches and template field; no
stored data format needs reverting, and no old session needs to be made loadable again.

## Open Questions

- Exact `stage_initial_sweeps` numeric values for `B1_WIDTH`/`B2_LOOKBACK` -- **explicit operator
  decision, not proposed by this design.** This change defines the field's shape and materialization
  semantics only.
- Exact `scientific_proposal.json` schema/filename for subsequent B1/B2 entries -- conceptual shape
  given in `proposal.md`, final field list and `contract_version` naming deferred to implementation,
  mirroring how `A_CONTROL`'s design deferred exact wording choices.
- Whether the component-insertion function belongs in `autoresearch_stage_contracts.py` (alongside
  `_strip_allowed`, its natural inverse) or in `autoresearch_supervisor.py` (alongside
  `_materialize_a_control_plan`) -- an implementation-time module-organization choice, not a
  behavior decision.
