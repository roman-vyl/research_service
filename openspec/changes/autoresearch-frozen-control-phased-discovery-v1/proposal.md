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
  `symmetric_measurement_geometry` dimension is removed from `A_BASELINE` and the frozen starting
  strategy's exit distance becomes the immutable control value for the rest of the session.
- `B1_WIDTH`, `B2_LOOKBACK`, and `B3_WIDTH_X_LOOKBACK` keep their existing typed dimensions (width,
  lookback, width×lookback) and now explicitly run under that same frozen control exit -- exit
  distance is not a free dimension anywhere in Phase B.
- **New stage** `C_ENTRY_REGION_SELECTION` (`entry_region_selection`): takes B3's structural result
  and requires the worker to shortlist 1-3 robust structural regions (not a single scalar winner)
  that carry forward into exit-geometry measurement, per the existing quality-policy promotion
  requirement.
- **New stage** `D_EXIT_GEOMETRY` (`exit_geometry`): scans symmetric ATR exit distance only across
  the shortlisted region(s) from `C_ENTRY_REGION_SELECTION` -- a small, already-narrowed
  width×lookback×distance space, not the original full parameter space. This is the first stage
  where economic metrics (PF, net/after-cost result, drawdown) become primary per the existing
  quality-policy requirement.
- Managed/dynamic exit logic (break-even, stop movement, profit locking, trailing, signal/event
  exits) is explicitly named as a future stage and explicitly **out of scope** for this change --
  no `exit_management.mode: "managed"` work is authorized here.
- `geometry_references`/`reference_strategy` and related stage-contract helpers are generalized so
  the "reference identity a worker must echo, not compute" pattern covers every symmetric exit
  distance a session measures (the single Phase A control value, and each configured distance swept
  per shortlisted region in `exit_geometry`). `structural_entry`/`structural_interaction` (width,
  lookback) stay continuous, worker-proposed dimensions with no fixed configured value set, as
  today -- this pattern is not extended to them.
- Stage-aware metric-role contracts already defined for `entry_region_selection` and `exit_geometry`
  in `autoresearch_quality_contracts.py` become reachable/enforced for the first time (they exist
  today but no stage contract ever reaches them).

## Capabilities

### New Capabilities

- `autoresearch-phased-discovery-v1`: the full six-stage AutoResearch causal program contract --
  frozen naked control (Phase A), independent structural discovery (B1/B2/B3), structural-region
  shortlisting (`entry_region_selection`), and symmetric exit-geometry measurement over the
  shortlist (`exit_geometry`) -- including the frozen-control invariant, the per-stage typed
  dimensions, and the shortlist-not-single-winner promotion contract between B3 and
  `entry_region_selection`.

### Modified Capabilities

(none -- `autoresearch-research-quality-policy-v1`'s existing requirements already describe this
six-stage behavior; this change makes the stage contract mechanism actually reach and enforce
`entry_region_selection`/`exit_geometry`, it does not change what those requirements say.)

## Impact

- `scripts/autoresearch_stage_contracts.py`: `STAGES`, `STAGE_DIMENSIONS`, `STAGE_PHASES`,
  `DIMENSIONS`, `validate_stage_contract`, `validate_resolved_stage_targets`,
  `reference_strategy`/`geometry_references` and their generalization, `validate_stage_request`.
- `scripts/autoresearch_quality_contracts.py`: no new requirements, but `entry_region_selection`/
  `exit_geometry` metric-role contracts go from unreachable to enforced; `describe_stage_metric_role_contract`
  needs no new cases (already covers both) but should be exercised by tests once reachable.
- `autoresearch/schemas/stage_contract.schema.json`, `autoresearch/schemas/execution_plan.v2.schema.json`:
  new stage enum values, new/changed dimension shapes for the frozen-control and shortlist stages.
- `autoresearch/templates/ema_anchor_stage_contract_session.json` and the starting-strategy fixture:
  frozen naked control fixed at 3.0/3.0 ATR instead of `measurement_geometries: [A-2, A-3, A-4]`.
- `autoresearch/prompts/planning.md`, `autoresearch/prompts/interpretation.md`,
  `autoresearch/program.md`, and the EMA-anchor domain skill: causal-sequence description, new
  stage names, shortlist instruction for `entry_region_selection`.
- `scripts/autoresearch_supervisor.py`: stage-context/geometry-id plumbing generalized to whichever
  dimension identifier the active stage uses.
- Test suites: `tests/test_autoresearch_stage_contract.py`, `tests/test_autoresearch_quality_policy.py`,
  `tests/test_autoresearch_supervisor.py`, `tests/test_autoresearch_program_contract.py`.
- No change to Research Service, Strategy Engine, or canonical execution/accounting semantics --
  this is entirely an AutoResearch harness-side sequencing change.
