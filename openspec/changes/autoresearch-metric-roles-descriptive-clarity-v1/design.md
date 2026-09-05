## Context

See `proposal.md` - Why. This design covers the exact per-stage-kind split between
harness-materialized `MetricRoles` content and worker-retained selection, derived from a full audit
of `validate_metric_roles()` (`scripts/autoresearch_quality_contracts.py:640-679`) against every
existing test fixture (`tests/test_autoresearch_quality_policy.py:121-158`) and one real HOST-smoke
`research_quality_assessment` (`var/autoresearch/ema-anchor-glm52-smoke-20260905155414/iterations/0001/iteration_result.json`).
All constants referenced below were re-read directly from
`scripts/autoresearch_quality_contracts.py` during this design pass (lines cited per constant).

## Goals / Non-Goals

**Goals:**
- Every `MetricRoles` field fully or mostly determined by stage_kind is materialized by the
  harness; the worker submits only fields the audit found to carry genuine evidentiary judgment.
- The complete materialized `MetricRoles` object still passes the unchanged
  `validate_metric_roles()` before the assessment is accepted -- no weakening of validation.
- `descriptive_baseline` requires zero worker `metric_roles` input (audit found nothing in that
  stage kind's constraints that isn't fully deterministic or mechanically meaningless).

**Non-Goals:**
- No change to `MetricRoles`' schema shape, `exact_role_names`, or `validate_metric_roles()`'s
  logic itself.
- No materialization of `GateResult`, `experiment`/`execution_result` blocks, `hypothesis`/
  `market_property_proxy` identity fields, or `TradeoffDimension.assessment` -- all found by the
  same audit to be separate, deferred candidates (see `proposal.md` - Impact).
- No fix to the unrelated `TradeoffComparison.relation_is_pareto_consistent` transient failure.
- No change to planning-side `B1_WIDTH`/`B2_LOOKBACK`/`A_CONTROL` materialization.

## Decisions

**Per-stage-kind materialized core and worker-retained selection**, confirmed against
`validate_metric_roles()`'s actual branches:

### `descriptive_baseline`

- `primary`: validator requires non-empty subset of `BASELINE_PRIMARY_ALLOWED`
  (`{realised_trade_count, open_position_count, long.trades, short.trades}`, `:121-126`) including
  `realised_trade_count`. All 4 members are always-available count facts from any completed batch
  (no candidate can lack them) -- **materialize the full set**, since citing more objective facts
  never harms and removes the ambiguity a worker faces choosing a subset (the real GLM smoke
  omitted `open_position_count` for no evident reason -- an artifact of guessing, not judgment).
- `secondary`: never inspected by the validator for this stage kind. Fixture uses `[]`.
  **Materialize `[]`.**
- `descriptive`: never inspected by the validator for this stage kind. The real GLM smoke put every
  other known metric name here (17 items) -- confirms this field has no worker-facing decision
  content for this stage. **Materialize as `CANONICAL_METRIC_PATHS - primary`** (deterministic
  complement, matching what a worker organically does when given no other guidance).
- `promotion_gates`: validator requires empty (`:650-651`). **Materialize `[]`.**
- **Worker submits: nothing.** No `metric_role_selection` needed for this stage kind.

### `structural_entry` / `structural_interaction` / `entry_region_selection`

- `primary` mandatory core: `response_topology` always required (`:659-660`); `neighborhood_stability`
  additionally required for `structural_interaction`/`entry_region_selection` (`:664-665`).
  **Materialize this core.**
- `primary` genuine choice: validator requires the union to intersect
  `CONDITIONAL_ENTRY_EVIDENCE` (`{baseline_uplift, win_rate, long.win_rate, short.win_rate}`,
  `:127-132`, checked `:657-658`) and `SAMPLE_THINNING_EVIDENCE` (`{realised_trade_count,
  thinning}`, `:133`, checked `:661-662`), and for the latter two stage kinds additionally
  `SIDE_BEHAVIOR_EVIDENCE` (`{long.win_rate, short.win_rate}`, `:134`, checked `:666-667`). No
  single canonical member of any of these sets is implied by stage alone -- which one(s) the worker
  judges reliable enough to cite this iteration is genuine evidentiary judgment (e.g. omitting
  `long.win_rate` when the long side has too few trades to trust is a real scientific call, not
  bureaucracy). **Worker submits: 1+ member from each of these three sets** (two sets for
  `structural_entry`, three for the other two stage kinds); harness unions them with the mandatory
  core, validates the result is a subset of `STRUCTURAL_PRIMARY_ALLOWED` before compiling.
- `secondary`: validator requires non-empty subset of `DESCRIPTIVE_ECONOMICS` (`:655`). Every
  fixture and the real smoke converge on exactly `{net_pnl, return_pct, profit_factor,
  max_drawdown}` with zero observed variance. **Materialize this fixed set** as the canonical
  value -- see Open Questions for the residual risk that this forecloses a real but never-yet-used
  choice.
- `descriptive`: never inspected by the validator. Fixture: `{gross_pnl, fees_paid}` --
  the raw accounting components (`net_pnl = gross_pnl - fees_paid`), distinct in kind from the
  headline economics in `secondary`. **Materialize `{gross_pnl, fees_paid}`.**
- `promotion_gates`: validator forbids `after_cost_positive` only (`:668-669`). No other constraint
  -- this genuinely varies per iteration's promotion claim. **Worker submits: the full
  `promotion_gates` list** (only this field, not the others), harness rejects it post-hoc if it
  includes the forbidden gate (unchanged validator behavior).

### `exit_geometry`

- `primary`: validator requires **exact equality** to `EXIT_PRIMARY` (13 members, `:147-161`,
  checked `:671-672`). Zero worker choice. **Materialize the full set.**
- `secondary`: never inspected by the validator for this stage kind (the `:655` check is scoped to
  the three structural stage kinds only -- confirmed by re-reading the `elif` structure). Fixture:
  `["win_rate"]`. **Materialize `["win_rate"]`** as the canonical value (only known signal of
  intended content; see Open Questions).
- `descriptive`: never inspected. Fixture: `{gross_pnl, fees_paid}`. **Materialize
  `{gross_pnl, fees_paid}`.**
- `promotion_gates`: validator requires `after_cost_positive` present (`:673-674`), no other
  constraint. **Worker submits: the full `promotion_gates` list** (only this field).

### `robustness_validation` (the `else` branch, `:675-679`)

- `primary` mandatory core: `ROBUSTNESS_PRIMARY` (6 members: `validation_evidence`,
  `neighborhood_stability`, `realised_trade_count`, `thinning`, `temporal_concentration`,
  `regime_concentration`, `:162-169`) always required. **Materialize this core.**
- `primary` genuine choice: `ROBUSTNESS_PRIMARY_ALLOWED - ROBUSTNESS_PRIMARY` (`response_topology,
  win_rate, long.trades, long.win_rate, short.trades, short.win_rate`, `:170-177`) is optional
  additional evidence -- genuine choice of what extra support to cite. **Worker submits: 0+ optional
  members from this set**; harness unions with mandatory core.
- `secondary`: never inspected. Fixture: `["net_pnl"]` (differs from the structural-stage
  convention -- confirms this field's content is stage-specific, not a shared derivation).
  **Materialize `["net_pnl"]`.**
- `descriptive`: never inspected. Fixture: `{gross_pnl, fees_paid}`. **Materialize
  `{gross_pnl, fees_paid}`.**
- `promotion_gates`: validator requires `after_cost_positive` present (`:678`), no other constraint.
  **Worker submits: the full `promotion_gates` list** (only this field).

**One shared materializer function, keyed on `stage_kind`, not per-branch copies.** Same rationale
as the planning-side `insert_bound_value`: a single source of truth for "given this stage_kind and
this worker selection, build the complete `MetricRoles`" avoids the cheat-sheet/validator drift that
caused the original bug.

**The narrow worker contract is `metric_role_selection`, not a smaller `MetricRoles`.** Shape
varies genuinely by stage kind (some stages need 2 evidence-set selections, some need optional
primary additions, all non-baseline stages need `promotion_gates`, baseline needs nothing) --
this is itself information the worker should not have to infer; the prompt states exactly which
selection fields apply to the active stage, mirroring how the narrowed B1/B2 `scientific_proposal`
prompt states exactly one mutable dimension.

## Risks / Trade-offs

- [Materializing `secondary`/`descriptive` as fixed values forecloses a legitimate future case
  where a worker would want a different split] → Mitigation: the audit found zero observed variance
  across every fixture and the one real smoke; if a future stage genuinely needs to vary these,
  that is itself evidence to revisit this decision, not a reason to preserve unused freedom now.
- [The materializer becomes a second place, alongside `validate_metric_roles()`, that must be kept
  in sync with the same stage-kind constants if those constants ever change] → Mitigation: same
  risk class as any materializer reusing validator-owned constants (accepted precedent from
  `_materialize_a_control_plan` reusing `reference_strategy()`); both read the same module-level
  constants directly, not independent copies.
- [Narrowing the worker-submitted shape requires either a new schema (`metric_role_selection`) or a
  looser `research_quality_assessment` schema accepting a partial `metric_roles` -- schema
  versioning choice not yet made] → Addressed in Open Questions below.

## Migration Plan

Additive/tightening at the mechanical layer, no `research_quality_assessment.schema.json` version
bump required in principle -- the final, materialized, fully-populated `MetricRoles` object
submitted to `validate_metric_roles()` has the exact same shape as today. What changes is the
worker-facing input contract (a narrower `metric_role_selection`) and where in the pipeline the full
object gets built. No stored artifact needs migration -- this only affects interpretation calls made
after this change ships.

## Open Questions

- Exact schema/artifact shape for `metric_role_selection` (new field inside the existing assessment
  input, or a separate small worker-authored object merged before validation) -- implementation
  detail, not fixed here.
- Whether `secondary` for `exit_geometry` (`["win_rate"]`) and `robustness_validation`
  (`["net_pnl"]`) should be re-derived from a principled rule (e.g. "one representative economics
  metric per stage") or simply hardcoded per stage as found in fixtures -- functionally identical
  for v1, but affects how obviously-intentional the choice reads to a future maintainer.
- Whether the mandatory `primary` core should also be validated as non-overlapping with the
  worker's optional selections before materialization (defensive check) or left to
  `validate_metric_roles()`'s existing disjointness/subset checks to catch downstream -- leaning
  toward the latter (reuse existing validation, don't duplicate it), confirm during implementation.
