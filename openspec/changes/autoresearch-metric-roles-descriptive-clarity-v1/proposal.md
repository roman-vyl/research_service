## Why

Two independent controlled HOST smokes this session (`A_CONTROL` with `claude-sonnet46`, then
`B1_WIDTH` first-entry with `glm52-opencode`, session `ema-anchor-glm52-b1-smoke-20260905160326`)
both hard-stopped on interpretation failures inside `research_quality_assessment` validation.
Investigation found a genuine worker-facing contract gap, not model unreliability:
`describe_stage_metric_role_contract()` (`scripts/autoresearch_quality_contracts.py:592-637`) --
the function whose own docstring says it renders "the one current stage's metric-role contract
that `validate_metric_roles` enforces... not a copy maintained by hand" -- tells the worker rules
for `metric_roles.primary`/`secondary`/`promotion_gates` in every one of its four stage-kind
branches (`descriptive_baseline`, `structural_entry`/`structural_interaction`/
`entry_region_selection`, `exit_geometry`, and the robustness-validation fallback), but never once
mentions `metric_roles.descriptive`.

`MetricRoles` (`scripts/autoresearch_quality_contracts.py:252-256`) requires `descriptive` as a
mandatory `list[str]` field, and `MetricRoles.exact_role_names` (`:258-272`) enforces that
`descriptive`/`primary`/`secondary` are pairwise disjoint. Because the prompt never tells the
worker what belongs in `descriptive` for any stage, a worker naturally duplicates an economics
metric it has already correctly placed in `secondary` (or `primary`) into `descriptive` too --
tripping the disjointness `ValueError("metric roles must be disjoint")`. This reproduced
identically across `glm52-opencode`'s interpretation retry 0 and retry 2 (3 total attempts, session
exhausted retries and hard-stopped). `validate_metric_roles()` (`:640-679`) independently confirms
the gap is structural, not accidental: none of its four stage branches inspect `roles.descriptive`
at all.

A second, unrelated validation error also appeared once (retry 1 only):
`TradeoffComparison.relation_is_pareto_consistent` (`:499-517`) rejected a `right_dominates`
relation whose per-dimension `assessment` values didn't Pareto-support it. This is a genuinely
separate, self-contained consistency check (relation vs. that same comparison's own dimension
assessments) with no connection to `metric_roles` -- investigated and confirmed not the same root
cause. It does not reproduce in the other two attempts and is not in scope for this change.

## What Changes

- `describe_stage_metric_role_contract()`'s cheat-sheet text for every stage kind gains an explicit
  statement of what `metric_roles.descriptive` must contain for that stage. Current design intent
  (confirmed against `validate_metric_roles()`, which never uses `descriptive` for any stage kind
  today) is that it must be empty everywhere -- background economics belong exclusively in
  `secondary` (structural stages) or are simply outside `metric_roles` entirely
  (`descriptive_baseline`, `exit_geometry`, robustness). The exact wording per stage is a design.md
  decision, not fixed here.
- `validate_metric_roles()` gains a matching mechanical check (`roles.descriptive` must be empty)
  for every stage kind it already handles -- defense in depth, matching this file's existing
  pattern of the worker-facing cheat-sheet and the mechanical validator being two views of one
  source of truth, not independently maintained.
- No change to `MetricRoles`' schema shape, `exact_role_names`' disjointness rule, or any other
  field/validator in `research_quality_assessment.schema.json`.
- The unrelated `TradeoffComparison.relation_is_pareto_consistent` transient failure is explicitly
  out of scope -- confirmed separate root cause, not folded into this fix.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `bbb-autoresearch-v1`: the interpretation worker's metric-role contract must be complete --
  every `MetricRoles` field the mechanical validator enforces must be explained to the worker, not
  left for the worker to infer from an incomplete cheat-sheet. `descriptive` was the field
  missing this coverage.

## Impact

- `scripts/autoresearch_quality_contracts.py`: `describe_stage_metric_role_contract()` and
  `validate_metric_roles()` both gain `descriptive`-field coverage, one function per stage-kind
  branch, four branches each.
- `autoresearch/prompts/interpretation.md`: no direct content change -- it already renders
  `{stage_metric_role_contract}` verbatim; the fix lives entirely in what that placeholder
  resolves to.
- No change to `B1_WIDTH`/`B2_LOOKBACK`/`A_CONTROL` planning-side materialization
  (`autoresearch-b1-b2-scientific-proposal-v1`, already implemented and separately verified this
  session) -- this change is interpretation-side only.
- No change to `B3_WIDTH_X_LOOKBACK`/`C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY`, evidence
  plots/renderer, worker profiles, or Research Service/Strategy Engine/Market Data Service
  production contracts.
- Existing regression safety net (`tests/test_autoresearch_quality_policy.py` if it exists, or the
  nearest equivalent covering `describe_stage_metric_role_contract`/`validate_metric_roles`) is
  expected to gain new coverage for the tightened contract in the implementation change, but is
  not modified by this proposal itself.
