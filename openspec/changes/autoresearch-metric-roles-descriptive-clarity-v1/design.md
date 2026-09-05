## Context

See `proposal.md` - Why. `describe_stage_metric_role_contract()`
(`scripts/autoresearch_quality_contracts.py:592-637`) renders the worker-facing cheat-sheet for
`metric_roles`; `validate_metric_roles()` (`:640-679`) is the mechanical enforcement the cheat-sheet
is supposed to mirror exactly (per the function's own docstring). Both currently omit `descriptive`
in all four stage-kind branches (`descriptive_baseline`; `structural_entry`/
`structural_interaction`/`entry_region_selection`; `exit_geometry`; the robustness-validation
fallback). This design covers closing that gap symmetrically in both functions.

## Goals / Non-Goals

**Goals:**
- Every stage kind's rendered contract text explicitly states what `metric_roles.descriptive` must
  contain.
- `validate_metric_roles()` mechanically enforces that same statement for every stage kind it
  already handles.
- No regression to any existing passing assessment: the fix must not reject a `descriptive` value
  that current production interpretation results already rely on.

**Non-Goals:**
- No change to `MetricRoles`' schema shape or `exact_role_names`' disjointness rule.
- No change to `metric_roles.primary`/`secondary`/`promotion_gates` rules for any stage.
- No fix to the unrelated `TradeoffComparison.relation_is_pareto_consistent` transient failure
  (confirmed separate root cause in `proposal.md` - Why).
- No change to `B1_WIDTH`/`B2_LOOKBACK`/`A_CONTROL` planning-side materialization.

## Decisions

**`descriptive` must be empty for every stage kind, stated explicitly in the cheat-sheet and
enforced mechanically.** Confirmed by reading `validate_metric_roles()`'s full body: no stage kind
branch reads or requires anything in `roles.descriptive` today -- every stage's background
economics already have an explicit, validated home (`secondary` for structural stages; implicitly
outside `metric_roles` for `descriptive_baseline`/`exit_geometry`/robustness, whose branches list
exhaustive `primary` requirements with no room for additional descriptive-only metrics). There is
no existing production use of a non-empty `descriptive` list this fix could break -- confirmed by
grepping test fixtures and any HOST smoke `iteration_result.json` on disk for a non-empty
`metric_roles.descriptive` (implementation task, not asserted here without checking). Alternative
considered: define real semantics for `descriptive` (e.g. "any additional context metric not used
for promotion") and explain those instead of forcing empty -- rejected as unnecessary scope
expansion; the actual failure this change fixes is ambiguity, and "empty, always" is the smallest
statement that removes it. If a future stage genuinely needs `descriptive` content, that is a
separate, deliberate change, not an accidental byproduct of this one.

**One shared per-stage-kind constant, not four independent string edits.** To keep the cheat-sheet
and the validator's mechanical check from drifting apart again the same way this gap arose,
implementation should introduce a single source of truth (e.g. a small stage-kind -> allowed-set
mapping, or simply the literal empty-list requirement stated once and referenced by both functions)
rather than editing four `if`/`elif` string blocks independently in each function. Exact shape is
an implementation detail.

## Risks / Trade-offs

- [Tightening `validate_metric_roles()` to reject non-empty `descriptive` breaks an existing session
  or fixture that currently (accidentally) passes with content there] → Mitigation: implementation
  task must grep existing `tests/test_autoresearch_quality_policy.py` fixtures and recent HOST smoke
  `iteration_result.json` artifacts under `var/autoresearch/` for any non-empty
  `metric_roles.descriptive` before tightening; if found, resolve explicitly (is it a legitimate
  historical value that changes this design's "always empty" assumption, or an existing
  never-caught mistake this fix should now catch) rather than silently overriding.
- [Prompt-only fix (cheat-sheet says "must be empty") without the matching mechanical tightening
  leaves the same class of gap for a future stage-kind addition that again forgets to update both
  places] → Mitigation: this design requires both changes together, not prompt-only.

## Migration Plan

Additive/tightening, no schema version bump: `research_quality_assessment.schema.json`'s shape is
unchanged (`descriptive` was already a plain `list[str]`); only the mechanical validator's
acceptance criteria narrow (empty required) and the worker-facing prompt text gains explicit
guidance. No stored artifact needs migration -- this only affects interpretation results produced
after this change ships. Rollback is reverting both function bodies; no data format changes.

## Open Questions

- Exact wording of the four (or fewer, if consolidated) cheat-sheet sentences -- implementation
  detail, not fixed here.
- Whether any existing fixture/smoke artifact already has non-empty `metric_roles.descriptive`
  (see Risks above) -- must be checked as an early implementation task before tightening
  `validate_metric_roles()`.
