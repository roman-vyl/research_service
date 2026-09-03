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

## Goals / Non-Goals

**Goals:**
- Freeze Phase A's exit distance to a single control value at session init; stop treating it as a
  scannable dimension.
- Add `C_ENTRY_REGION_SELECTION` and `D_EXIT_GEOMETRY` as real stages in `STAGES`, with their own
  `STAGE_DIMENSIONS`/`STAGE_PHASES` entries wired to the already-existing `entry_region_selection`/
  `exit_geometry` `StageKind`s.
- Extend the geometry-reference-hash pattern (session-state-published, supervisor-recomputed) to
  cover the shortlisted-region × distance space `exit_geometry` scans.
- Keep B1/B2/B3 mechanically unchanged except: bind their exit distance to the new frozen control
  value instead of leaving it unconstrained/implicit.

**Non-Goals:**
- Redesigning how B1/B2/B3 propose or validate width/lookback candidates (still continuous,
  worker-proposed, no configured value list).
- Any managed/dynamic exit stage (`D` in the user's numbering here is `exit_geometry`; the
  eventual managed-exit stage is unnamed and explicitly deferred).
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
phase). Both new phase strings already exist in the template's `phase_bindings` today.

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
`A_CONTROL` for schema uniformity with `D_EXIT_GEOMETRY`. Rejected -- a list that can only ever
have exactly one element is a worse contract than no list; the `_exact` one-candidate-per-stage
check already enforces "measure once."

### 3. `D_EXIT_GEOMETRY`'s configured value set is keyed by `(region_id, distance)`, not distance alone

`exit_geometry` sweeps distance independently per shortlisted region (proposal: "B left width
0.6-0.9, lookback 4-7" and C adds a distance list *for that region*; a second shortlisted region
gets its own independent distance sweep over the same fixed starting strategy plus that region's
width/lookback). The stage contract's per-value reference-hash list therefore keys each entry by
`{region_id, geometry_id, distance, resolved_sha256}` rather than `{geometry_id, distance}` alone,
where `region_id` identifies the specific shortlisted `entry_region_selection` output being
measured. `reference_strategy(state, region_id, geometry_id)` builds the candidate strategy from
the frozen naked baseline plus that region's fixed width/lookback plus that geometry's distance --
generalizing today's `reference_strategy(state, geometry_id)` (which only applies the exit
distance) to also apply the region's structural dimensions.

Alternative considered: one shared distance list applied identically to every shortlisted region
(no `region_id` key). Rejected -- nothing requires two shortlisted regions to be swept at the same
distances, and collapsing them would make `exit_geometry` implicitly assume every region needs
identical resolution, which is a scientific claim the harness should not make for the worker.

### 4. `entry_region_selection`'s shortlist is a new state field, not reused `phase_a_references`

`phase_a_references` today means "one accepted measurement per `symmetric_measurement_geometry`
value in `A_BASELINE`." Renaming/repurposing it to also mean "structural regions shortlisted out of
B3" would conflate two different provenance shapes (a single strategy-level measurement vs. a
width/lookback region with its own boundary). A new `entry_regions` state list holds shortlisted
region entries (`region_id`, width range, lookback range, structural evidence refs, accepted
iteration), 1-3 per session per the spec. `phase_a_references` is kept for `A_CONTROL`'s own single
measurement (renamed in meaning but not shape: one entry, one strategy-level provenance record).

### 5. Causal-order enforcement reuses the existing `prerequisite_disposition_refs`/`required_stages` mechanism, extended by one row each

`validate_stage_context`'s `required_stages` mapping (stage -> set of prior stages that must be
`characterized`/`terminally_rejected` before this stage is reachable) already generalizes cleanly:
`C_ENTRY_REGION_SELECTION: {A_CONTROL, B1_WIDTH, B2_LOOKBACK, B3_WIDTH_X_LOOKBACK}`,
`D_EXIT_GEOMETRY: {..., C_ENTRY_REGION_SELECTION}`. No new mechanism needed here, just two new
rows -- this also closes the still-open `prerequisite_disposition_refs` prompt-explanation gap
identified in the same controlled HOST smoke that motivated this change, since the new stages make
that field non-trivial (non-empty) for the first time in practice and the planning prompt must
finally explain what it means, not just render the raw JSON.

## Risks / Trade-offs

- **[Risk]** Six stages is a bigger causal-order surface for a planning worker to reason about
  correctly than four. → **Mitigation**: `describe_stage_metric_role_contract` and the
  `prerequisite_disposition_refs` prompt explanation (Decision 5) already exist/are being added;
  extend both to the two new stages rather than inventing new prompt mechanisms.
- **[Risk]** Multiple shortlisted regions in `entry_region_selection` multiply
  `D_EXIT_GEOMETRY`'s batch count (each region gets its own distance sweep). → **Mitigation**: cap
  shortlist size at 3 per the spec requirement; this is a bounded, small multiplier, not unbounded
  fan-out.
- **[Risk]** Renaming `A_BASELINE` -> `A_CONTROL` breaks any code, fixture, or session-in-flight
  that hardcodes the old name. → **Mitigation**: see Migration Plan; this is a session-schema-major
  change already (v3 stage contract), sessions in flight on the old contract are not migrated.

## Migration Plan

This changes the stage contract's shape (new stages, removed `A_BASELINE` geometry scan, renamed
identifiers) -- it is not backward compatible with `bbb_autoresearch_stage_contract.v1` sessions.
No in-place migration is planned:

1. Bump `STAGE_CONTRACT_VERSION` (and any other version constants whose shape changes) so old and
   new sessions fail closed against each other, matching the existing "no silent migration" pattern
   already used for `bbb_autoresearch_state.v1/v2/v3`.
2. Existing `var/autoresearch/<session_id>/` sessions built on the old 4-stage contract are left as
   historical/read-only records; new sessions after this change use the new template/fixture.
3. Rollback is: revert the code/schema/template changes; already-created new-contract sessions
   would then fail to resume (acceptable, since AutoResearch sessions are disposable research runs,
   not production data).

## Open Questions

None -- the shortlist size bound (1-3), the frozen-control mechanism, and the reference-identity
scope were resolved above rather than deferred.
