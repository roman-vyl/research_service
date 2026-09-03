## Context

See `proposal.md` - Why. The relevant current mechanics:

- `scripts/autoresearch_stage_contracts.py` defines `STAGES = (A_BASELINE, B1_WIDTH, B2_LOOKBACK,
  B3_WIDTH_X_LOOKBACK)`, `DIMENSIONS` (`symmetric_measurement_geometry`, `anchor_stack_width`,
  `untouched_anchor_lookback`), `STAGE_DIMENSIONS` (which dimensions each stage may vary), and
  `STAGE_PHASES` (stage -> quality-policy phase string).
- Only `symmetric_measurement_geometry` has a *fixed configured value set* today
  (`measurement_geometries: [A-2, A-3, A-4]` in the stage contract, each with a published
  `geometry_references` reference hash the worker must echo). `anchor_stack_width` and
  `untouched_anchor_lookback` are continuous, worker-proposed values with no such list -- a
  planning worker may propose any width/lookback value for B1/B2/B3 today, and that does not
  change here.
- `autoresearch_quality_contracts.py`'s `StageKind` already has six values (`descriptive_baseline`,
  `structural_entry`, `structural_interaction`, `entry_region_selection`, `exit_geometry`,
  `robustness_validation`) and `describe_stage_metric_role_contract`/`validate_metric_roles`
  already implement rules for `entry_region_selection` and `exit_geometry`. Nothing in
  `autoresearch_stage_contracts.py` ever reaches those two stage kinds today -- the stage contract
  stops at `B3_WIDTH_X_LOOKBACK`.
- `phase_a_references` in session state currently accumulates one entry per measured
  `symmetric_measurement_geometry` value (A-2, then A-3, then A-4) with realised evidence
  provenance (receipt sha, run id, market data hash, trade count, win rate).

## Revision note

This design was corrected after a review of the first implementation pass (Parts 1-4). Two
substantive mistakes from that pass are fixed here rather than silently carried forward:

1. **B2_LOOKBACK must not require B1_WIDTH closed.** The first pass's causal graph had B2 depending
   on B1 (a straight line A -> B1 -> B2 -> B3). The correct graph is A -> {B1, B2} independently,
   both feeding into B3:

   ```
   A_CONTROL
      │
      ├────> B1_WIDTH ──────┐
      │                     │
      └────> B2_LOOKBACK ───┴──> B3_WIDTH_X_LOOKBACK
   ```

   Running B1 before B2 in a given session is process serialization by a single-worker-at-a-time
   harness -- it was never a causal dependency, and the stage contract must not enforce one.

2. **`entry_region_selection`/`exit_geometry` are reserved names, not implemented stages.** The
   first pass (wrongly) designed their full behavioral contract -- a region shape, a shortlist
   acceptance rule, a `(region_id, geometry_id, distance)` reference-hash mechanism -- before ever
   observing what a real B1/B2/B3 evidence run actually produces. That is designing blind. Both
   stages keep their names and `StageKind`/phase-string bindings (stable, harmless to commit to
   now), but their state shape, transition rules, and execution semantics are explicitly deferred
   to a follow-up change once real HOST-run evidence exists to design against. No plan may target
   either stage in the meantime; see Decision 3 (revised) below. Decisions 3 and 4 from the original
   version of this document (the region-scoped reference-hash mechanism and the `entry_regions`
   state field) are removed, not merely deferred in wording -- they described a contract this change
   does not implement and should not appear settled.

## Goals / Non-Goals

**Goals:**
- Freeze Phase A's exit distance to a single control value at session init; stop treating it as a
  scannable dimension.
- Fix the B-stage causal graph: B1_WIDTH and B2_LOOKBACK each depend only on A_CONTROL, independent
  of each other; B3_WIDTH_X_LOOKBACK depends on both.
- Reserve `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` as stage names and phase bindings (wired to
  the already-existing `entry_region_selection`/`exit_geometry` `StageKind`s), while making them
  unreachable for execution -- no plan may target them, and no stage transition may enter them
  automatically -- until a follow-up change defines their contract from real evidence.
- Keep B1/B2/B3 mechanically unchanged except: bind their exit distance to the new frozen control
  value instead of leaving it unconstrained/implicit.

**Non-Goals:**
- Redesigning how B1/B2/B3 propose or validate width/lookback candidates (still continuous,
  worker-proposed, no configured value list).
- Defining `entry_region_selection`/`exit_geometry` behavior, state shape, or a reference-identity
  mechanism for either -- explicitly deferred (see Revision note).
- Any managed/dynamic exit stage -- unnamed, unreserved, explicitly out of scope.
- Changing Research Service, Strategy Engine, or canonical execution/accounting behavior.
- Migrating or reinterpreting any already-recorded session (see Migration Plan).

## Decisions

### 1. Rename stage identifiers to `A_CONTROL`/`B1_WIDTH`/`B2_LOOKBACK`/`B3_WIDTH_X_LOOKBACK`/`C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY`

Alternative considered: keep `A_BASELINE` as the name and just strip its dimension. Rejected --
`A_BASELINE` today *is* the geometry-scan stage in every schema, prompt, and test; keeping the name
while gutting its behavior invites exactly the kind of silent contract drift this whole change is
trying to close (cf. the branch-mismatch/lost-fix incident earlier in this session). A renamed
stage forces every touch point (schemas, prompts, fixtures, tests) to be updated deliberately
instead of silently reinterpreted.

`STAGES` becomes a 6-tuple; `STAGE_PHASES` maps `A_CONTROL -> "baseline"` (unchanged from today --
the template's `research_quality_policy.phase_bindings` already binds `"baseline"` to
`descriptive_baseline`, so the phase string does not need to change, only the stage's dimension
set), `C_ENTRY_REGION_SELECTION -> "entry_region_selection"`, `D_EXIT_GEOMETRY -> "exit_geometry"`
(matching the `StageKind` string exactly, unlike the existing `B1_WIDTH`/`B2_LOOKBACK ->
"structural_1d"` indirection, since these two new stages have no B1/B2-style siblings sharing one
phase). Both new phase strings already exist in the template's `phase_bindings` today. Reserving
the name/phase-binding pair now is cheap and stable regardless of what C/D's eventual contract
turns out to be; it does not presume anything about their execution semantics.

### 2. Phase A control value lives in the stage contract's `starting_strategy`, not a new field

The frozen strategy fixture already carries its exit distance inside
`starting_strategy.strategy.raw_spec.trade_management.exit_policy...distance.multiplier`. Rather
than introduce a parallel "control_distance" field that could drift from the fixture, `A_CONTROL`'s
single measured value *is* the frozen starting strategy as-is -- no `measurement_geometries` list,
no per-geometry reference hash list, just the existing single `starting_strategy.resolved_sha256`
(already published, already echoed by workers). `geometry_references` (plural, per-geometry) is
removed from `A_CONTROL`'s contract entirely; the existing single `resolved_sha256` echo is
sufficient because there is only one value to measure.

Alternative considered: keep a one-element `measurement_geometries`/`geometry_references` list for
`A_CONTROL` for schema uniformity with a possible future `D_EXIT_GEOMETRY`. Rejected -- a list that
can only ever have exactly one element is a worse contract than no list; the `_exact`
one-candidate-per-stage check already enforces "measure once."

### 3. C_ENTRY_REGION_SELECTION/D_EXIT_GEOMETRY are fail-closed unreachable, not merely undocumented

`validate_stage_context` rejects any plan whose `active_stage` is one of `PROVISIONAL_STAGES =
(C_ENTRY_REGION_SELECTION, D_EXIT_GEOMETRY)` with an explicit "execution semantics are not yet
defined" error, before it would otherwise look up `STAGE_DIMENSIONS`/`required_stages` for that
stage (which no longer have entries for either -- looking one up is itself a signal something
presumed a contract that doesn't exist). `_advance_state` never sets `active_stage` to either
value: closing B3 leaves `active_stage` at `B3_WIDTH_X_LOOKBACK`, and a worker that proposes no
further experiment reaches ordinary terminal `completed` status from there, not a stage transition.
`validate_state` additionally rejects a durable state whose `active_stage` is already one of the
provisional stages, as defense in depth against a hand-edited `state.json`.

Alternative considered (the original Decision 3/4 from the first pass of this document): fully
design C's shortlist acceptance and D's `(region_id, geometry_id, distance)` reference-hash
mechanism now, reusing the `geometry_references` pattern. Rejected per the Revision note above --
we have not yet observed what a real B1/B2/B3 evidence run durably needs to carry into a shortlist,
and designing that shape from imagination risks building a contract nobody's actual evidence fits.
That design work is real and belongs in a follow-up change, informed by a HOST research run through
A/B1/B2/B3.

### 4. Causal-order enforcement reuses the existing `prerequisite_disposition_refs`/`required_stages` mechanism, with a corrected graph

`validate_stage_context`'s `required_stages` mapping (stage -> set of prior stages that must be
`characterized`/`terminally_rejected` before this stage is reachable) now reads:

```
A_CONTROL:           {}
B1_WIDTH:             {A_CONTROL}
B2_LOOKBACK:          {A_CONTROL}
B3_WIDTH_X_LOOKBACK:  {A_CONTROL, B1_WIDTH, B2_LOOKBACK}
```

No row exists for `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` (Decision 3 rejects them earlier, so
a `required_stages` lookup for either is unreachable code, not merely unused). This also closes the
still-open `prerequisite_disposition_refs` prompt-explanation gap identified in the controlled HOST
smoke that originally motivated this change -- the field is non-trivial (non-empty) starting at B1,
and the planning prompt should explain what it means rather than only render the raw JSON (tracked
as a task, not yet done in this part).

### 5. `terminally_rejected` does not block a sibling or downstream stage (exploratory, not strict)

Whether B3 should run if B1 or B2's own result was `terminally_rejected` is a live open methodology
question (see Open Questions). The mechanism as implemented today is *exploratory*: `required_stages`
and the durable "closed" check both treat `characterized` and `terminally_rejected` as equally
"closed" -- either satisfies a downstream prerequisite. This was not a deliberate methodology choice
made in this change; it falls out of reusing the existing disposition-closing mechanism unchanged.
It is flagged here explicitly rather than left to be discovered later, and the operator should treat
it as provisional until Open Questions below is resolved.

## Risks / Trade-offs

- **[Risk]** Even four stages (A, B1, B2, B3) is real causal-order surface for a planning worker to
  reason about correctly, and B1/B2 independence adds a "which branch am I in" question the old
  linear graph didn't have. → **Mitigation**: the `prerequisite_disposition_refs` prompt-explanation
  task (Decision 4) should make the durable-prerequisite set legible per stage, not just per a
  single linear position.
- **[Risk]** Reserving `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` as names now, before their
  contract exists, risks the names quietly shaping the eventual design (anchoring bias) even though
  no behavior is defined. → **Mitigation**: none beyond awareness; the alternative (not reserving
  names at all) reopens the phase-binding/StageKind wiring question this change already closed
  cheaply, which seems like a worse trade.
- **[Risk]** Renaming `A_BASELINE` -> `A_CONTROL` breaks any code, fixture, or session-in-flight
  that hardcodes the old name. → **Mitigation**: see Migration Plan; this is a session-schema-major
  change already (v3 stage contract), sessions in flight on the old contract are not migrated.

## Migration Plan

This changes the stage contract's shape (new B-graph, removed `A_BASELINE` geometry scan, renamed
identifiers) -- it is not backward compatible with `bbb_autoresearch_stage_contract.v1` sessions.
No in-place migration is planned:

1. Bump `STAGE_CONTRACT_VERSION` (and any other version constants whose shape changes) so old and
   new sessions fail closed against each other, matching the existing "no silent migration" pattern
   already used for `bbb_autoresearch_state.v1/v2/v3`. (Done: `v1` -> `v2`.)
2. Existing `var/autoresearch/<session_id>/` sessions built on the old contract are left as
   historical/read-only records; new sessions after this change use the new template/fixture.
3. Rollback is: revert the code/schema/template changes; already-created new-contract sessions
   would then fail to resume (acceptable, since AutoResearch sessions are disposable research runs,
   not production data).

## Open Questions

- **Strict vs. exploratory B3 eligibility**: should `B3_WIDTH_X_LOOKBACK` require both B1 and B2 to
  have found a promising region (strict), or is either's `terminally_rejected` status still
  sufficient to proceed because an interaction can exist without a strong marginal effect
  (exploratory, the current de-facto behavior per Decision 5)? This is a research-methodology
  decision, not an engineering one, and should be made consciously -- by the operator, informed by
  what A/B1/B2 evidence actually looks like -- before or during the first real B3 run, not assumed
  from the current implementation.
- **What is a durable "B1 result" / "B2 result"?** Not just a `characterized` disposition status --
  B3 (and any future C) plausibly needs the investigated range, promising interval(s)/plateau
  (response *shape*, not a single optimum point), rejected ranges, and evidence/provenance per
  branch, carried durably rather than re-derived. This change does not define that durable shape;
  it is a prerequisite for designing `entry_region_selection` properly and belongs in the follow-up
  change referenced in Decision 3, informed by what a real B1/B2 run actually produces.
