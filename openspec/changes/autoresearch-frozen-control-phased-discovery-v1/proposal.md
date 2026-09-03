## Why

The current AutoResearch stage contract (`autoresearch_stage_contracts.py`) implements only four
stages (`A_BASELINE`, `B1_WIDTH`, `B2_LOOKBACK`, `B3_WIDTH_X_LOOKBACK`), and `A_BASELINE` treats the
symmetric exit distance itself as the thing being measured/scanned (three configured geometries
A-2/A-3/A-4). This conflates two independent questions -- "does a structural entry filter carry
information?" and "at what excursion scale does the resulting market state pay off?" -- into one
dimensionality from the very first stage, and risks a structural discovery (B1/B2/B3) that is
secretly confounded with whatever exit distance happened to be scanned alongside it.

This is also a regression relative to already-declared intent: the sibling
`autoresearch-research-quality-policy-v1` capability already defines six `StageKind` values --
`descriptive_baseline`, `structural_entry`, `structural_interaction`, `entry_region_selection`,
`exit_geometry`, `robustness_validation` -- and already requires (`Phase B prioritizes conditional
entry quality`) that `structural_entry`/`structural_interaction` run "under one fixed neutral
symmetric exit," and (`Entry-region selection promotes structural regions into exit geometry`) that
symmetric-exit economics only become primary once a structural region reaches `exit_geometry`. The
stage contract mechanism never wired `entry_region_selection` or `exit_geometry` up as real,
runnable stages with typed dimensions -- it stops at `B3_WIDTH_X_LOOKBACK` and never freezes exit
geometry at a single control value in Phase A to begin with.

A controlled HOST smoke confirmed the discovery-worker mechanics work end to end on the current
four-stage contract (A-2 measured, evidence validated, journal/state committed), but also that
continuing past A-2 into a genuinely comparative three-geometry Phase A adds real interpretive
weight the harness was never asked to carry: reconciling A-2/A-3/A-4 against each other without
treating exit distance as an optimization target. Freezing Phase A removes that ambiguity at the
source instead of asking the harness (or the interpretation worker) to police it after the fact.

## What Changes

- Phase A (`descriptive_baseline`) becomes a single frozen naked control at one pre-chosen neutral
  symmetric ATR distance (3.0/3.0), not a three-point geometry scan. The stage contract's
  `symmetric_measurement_geometry` dimension is removed from `A_BASELINE` (renamed `A_CONTROL`) and
  the frozen starting strategy's exit distance becomes the immutable control value for the rest of
  the session.
- `B1_WIDTH` and `B2_LOOKBACK` each depend only on the closed `A_CONTROL` reference and are
  independent of each other (neither is a prerequisite of the other); `B3_WIDTH_X_LOOKBACK` depends
  on both durably closed. All three keep their existing typed dimensions (width, lookback,
  width×lookback) and now explicitly run under that same frozen control exit -- exit distance is
  not a free dimension anywhere in Phase B.
- **Reserved, not implemented**: `C_ENTRY_REGION_SELECTION` (`entry_region_selection`) and
  `D_EXIT_GEOMETRY` (`exit_geometry`) exist as stage names and `StageKind`/phase-string bindings
  only. Their behavioral contract -- what a durable B1/B2 "result" looks like, the shortlist
  acceptance rule, any exit-distance sweep mechanism -- is explicitly deferred to a follow-up
  change, informed by real evidence from a HOST run through A/B1/B2/B3. No plan may target either
  stage, and no stage transition may enter them automatically; the harness fails closed instead.
- Managed/dynamic exit logic (break-even, stop movement, profit locking, trailing, signal/event
  exits) is explicitly named as a future, unreserved stage and explicitly **out of scope** for this
  change -- no `exit_management.mode: "managed"` work is authorized here.
- Stage-aware metric-role contracts already defined for `entry_region_selection` and `exit_geometry`
  in `autoresearch_quality_contracts.py` remain unreachable (unchanged from today) since no plan can
  target either stage yet; they will become reachable once the follow-up change defines those
  stages' execution semantics.

## Capabilities

### New Capabilities

- `autoresearch-phased-discovery-v1`: the AutoResearch causal program contract for Phase A and
  Phase B -- frozen naked control (Phase A), independent structural discovery branches B1
  (width) and B2 (lookback) off that control, and their interaction B3 -- including the
  frozen-control invariant, the corrected B1/B2 independence graph, and the reserved-but-unreachable
  `entry_region_selection`/`exit_geometry` stage names for a later change to define.

### Modified Capabilities

(none -- `autoresearch-research-quality-policy-v1`'s existing requirements already describe the
six-`StageKind` program; this change does not touch what those requirements say, and does not yet
make the two downstream stage kinds reachable.)

## Impact

- `scripts/autoresearch_stage_contracts.py`: `STAGES`, `STAGE_DIMENSIONS`, `STAGE_PHASES`,
  `PROVISIONAL_STAGES`, `DIMENSIONS`, `validate_stage_contract`, `validate_resolved_stage_targets`,
  `reference_strategy`, `validate_stage_context`, `validate_stage_request`.
- `scripts/autoresearch_quality_contracts.py`: unchanged -- `entry_region_selection`/`exit_geometry`
  metric-role contracts remain defined-but-unreachable, same as before this change.
- `autoresearch/schemas/stage_contract.schema.json`, `autoresearch/schemas/execution_plan.v2.schema.json`,
  `autoresearch/schemas/session_state.v3.schema.json`, `autoresearch/schemas/journal_event.v3.schema.json`,
  `autoresearch/schemas/iteration_result.v3.schema.json`: new stage enum values (names reserved,
  behavior undefined for the two reserved ones), removed `measurement_geometries`/
  `geometry_references` shape.
- `autoresearch/templates/ema_anchor_stage_contract_session.json` and the starting-strategy fixture:
  frozen naked control fixed at 3.0/3.0 ATR instead of `measurement_geometries: [A-2, A-3, A-4]`.
- `autoresearch/prompts/planning.md` and `autoresearch/program.md`: causal-sequence description,
  new stage names, frozen-control framing.
- `scripts/autoresearch_supervisor.py`: `phase_a_references`/`stage_history`/journal-event shapes
  drop per-geometry keying (single control measurement); durable closed-stage invariants and
  stage-transition logic corrected to the B1/B2-independent graph and to never auto-enter the
  reserved stages.
- Test suites: `tests/test_autoresearch_stage_contract.py`, `tests/test_autoresearch_supervisor.py`,
  `tests/test_autoresearch_quality_policy.py`, `tests/test_autoresearch_state.py`,
  `tests/test_autoresearch_program_contract.py`, `tests/test_autoresearch_guard.py`,
  `tests/test_autoresearch_execute_batch.py`, `tests/test_autoresearch_strategy_spec_reference.py`,
  `tests/test_batch_experiments.py`.
- No change to Research Service, Strategy Engine, or canonical execution/accounting semantics --
  this is entirely an AutoResearch harness-side sequencing change.
