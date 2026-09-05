## Why

Two independent controlled HOST smokes this session (`A_CONTROL` with `claude-sonnet46`, then
`B1_WIDTH` first-entry with `glm52-opencode`, session `ema-anchor-glm52-b1-smoke-20260905160326`)
both hard-stopped on interpretation failures inside `research_quality_assessment` validation.
Investigation found a genuine worker-facing contract gap: `describe_stage_metric_role_contract()`
(`scripts/autoresearch_quality_contracts.py:592-637`) -- the function whose own docstring says it
renders "the one current stage's metric-role contract that `validate_metric_roles` enforces... not
a copy maintained by hand" -- tells the worker rules for `metric_roles.primary`/`secondary`/
`promotion_gates` in every one of its stage-kind branches (`descriptive_baseline`,
`structural_entry`/`structural_interaction`/`entry_region_selection`, `exit_geometry`,
`robustness_validation`), but never once mentions `metric_roles.descriptive`.
`MetricRoles.exact_role_names` (`:258-272`) enforces that `descriptive`/`primary`/`secondary` are
pairwise disjoint. Because the prompt never tells the worker what belongs in `descriptive`, a worker
naturally duplicates an economics metric already correctly placed in `secondary`/`primary` into
`descriptive` too -- tripping `ValueError("metric roles must be disjoint")`. This reproduced
identically across `glm52-opencode`'s interpretation retry 0 and retry 2 (3 total attempts, session
exhausted retries and hard-stopped).

**This reproduction is unchanged from the original finding. What changed is the diagnosis of the
correct fix**, after auditing every `MetricRoles` field against `validate_metric_roles()` and every
existing test fixture / a real HOST-smoke-produced assessment
(`var/autoresearch/ema-anchor-glm52-smoke-20260905155414/iterations/0001/iteration_result.json`,
GLM 5.2's actual `descriptive_baseline` output): the original plan (teach the worker a more complete
cheat-sheet, including what `descriptive` should contain) treats a mostly-mechanical field as if it
required better worker-facing documentation. It does not. The audit found:

- `exit_geometry`'s `primary` must already equal `EXIT_PRIMARY` **exactly** -- zero worker choice,
  fully deterministic today, and the worker is still asked to hand-type the full set.
- `descriptive_baseline`'s `promotion_gates` must already be empty -- fully deterministic.
- `robustness_validation`'s `primary` has a **mandatory core** (`ROBUSTNESS_PRIMARY`, exactly 4
  names) that must always be present, with only the remaining `ROBUSTNESS_PRIMARY_ALLOWED -
  ROBUSTNESS_PRIMARY` members genuinely optional.
- `structural_entry`/`structural_interaction`/`entry_region_selection`'s `primary` has a mandatory
  core (`response_topology`, plus `neighborhood_stability` for the latter two) and a real "at least
  one of" choice from `CONDITIONAL_ENTRY_EVIDENCE`/`SAMPLE_THINNING_EVIDENCE`/
  `SIDE_BEHAVIOR_EVIDENCE` -- this is the one place genuine evidentiary judgment survives (which
  specific named evidence the worker judges reliable enough to cite this iteration).
- `secondary` and `descriptive` are **never inspected by `validate_metric_roles()` for any stage
  kind** except a loose "non-empty subset of `DESCRIPTIVE_ECONOMICS`" check on `secondary` for the
  three structural stage kinds only (`:655`) -- yet every existing test fixture
  (`tests/test_autoresearch_quality_policy.py:121-158`) and the one real GLM smoke both converge on
  the same stable values per stage kind with zero observed variance, strongly indicating these
  fields carry no scientific content the worker is actually deciding.
- `promotion_gates` beyond its mandatory include/exclude constraints is the other place with
  legitimate per-iteration freedom (which additional gates are relevant to this iteration's
  promotion claim).

Per the standing principle established during the planning-side redesign (`A_CONTROL`/
`B1_WIDTH`/`B2_LOOKBACK` materialization, already shipped/in-progress): **if a field can be
unambiguously derived from active stage and frozen policy, the worker must not be required to
generate it.** A more detailed cheat-sheet asks the worker to keep correctly hand-typing a
structure the harness can build deterministically; it does not remove the underlying bureaucratic
burden, only documents it better. This change replaces the cheat-sheet-only fix with a
deterministic `metric_roles` materializer, mirroring the planning-side WHAT/HOW split.

A second, unrelated validation error also appeared once (retry 1 only):
`TradeoffComparison.relation_is_pareto_consistent` (`:499-517`) rejected a `right_dominates`
relation whose per-dimension `assessment` values didn't Pareto-support it -- confirmed a separate,
self-contained root cause, not folded into this change.

## What Changes

- A new deterministic `metric_roles` materializer builds every fixed/derivable role assignment from
  `active_stage`/`stage_kind` alone, using the existing Python constants in
  `scripts/autoresearch_quality_contracts.py` (`DESCRIPTIVE_ECONOMICS`, `BASELINE_PRIMARY_ALLOWED`,
  `STRUCTURAL_PRIMARY_ALLOWED`, `CONDITIONAL_ENTRY_EVIDENCE`, `SAMPLE_THINNING_EVIDENCE`,
  `SIDE_BEHAVIOR_EVIDENCE`, `EXIT_PRIMARY`, `ROBUSTNESS_PRIMARY`, `ROBUSTNESS_PRIMARY_ALLOWED`) --
  these constants already ARE the canonical stage quality policy in code form; this change exposes
  them as a materializable value instead of leaving them as validation-only constraints the worker
  must independently satisfy by guessing.
- The worker's `research_quality_assessment` submission narrows to a `metric_role_selection` --
  scientific content only, covering exactly the fields the audit found to carry genuine evidentiary
  judgment: for `structural_entry`/`structural_interaction`/`entry_region_selection`, which specific
  member(s) of `CONDITIONAL_ENTRY_EVIDENCE`/`SAMPLE_THINNING_EVIDENCE`/(`SIDE_BEHAVIOR_EVIDENCE`
  where applicable) to name; for `robustness_validation`, which optional members of
  `ROBUSTNESS_PRIMARY_ALLOWED - ROBUSTNESS_PRIMARY` to include; for every non-baseline stage, which
  additional `promotion_gates` beyond the mandatory include/exclude constraints apply this
  iteration. `descriptive_baseline` requires no worker `metric_role_selection` input at all -- every
  field the audit checked for that stage kind was fully deterministic or carried zero mechanical
  meaning.
- The harness compiles the worker's narrow selection plus the deterministic core into the full
  `MetricRoles` object before the existing `validate_metric_roles()` runs -- **that validator is
  reused completely unchanged as an independent post-hoc defense**, exactly the pattern already
  established for the planning-side materializer (`_materialize_a_control_plan`/
  `insert_bound_value` reusing `validate_stage_request`/`_strip_allowed` unchanged).
- No change to `MetricRoles`' schema shape or `exact_role_names`' disjointness rule.
- The unrelated `TradeoffComparison.relation_is_pareto_consistent` transient failure remains
  explicitly out of scope.
- Explicitly deferred as separate follow-up findings, not part of this change (see Impact):
  `GateResult` inside `economic_viability` (found by the same audit to be almost entirely
  harness-derivable from `policy.promotion_thresholds` + `candidate_facts`), the `experiment`/
  `execution_result` blocks' near-verbatim duplication of `canonical_request.json`/
  `execution_receipt.json`, the `hypothesis`/`market_property_proxy` identity fields (already
  partially addressed by the existing post-hoc `_materialize_interpretation_identity` overwrite),
  and `TradeoffDimension.assessment` for metric-based dimensions.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `bbb-autoresearch-v1`: the interpretation worker is no longer required to author any
  `metric_roles` content that is fully or mostly determined by the active stage's fixed quality
  policy; the worker retains only the narrow selections where genuine evidentiary judgment exists.
  The harness deterministically materializes the remainder and the existing mechanical validator
  continues to enforce the complete result unchanged.

## Impact

- `scripts/autoresearch_quality_contracts.py`: new materializer function(s) building the
  stage-appropriate fixed `MetricRoles` core; `validate_metric_roles()` itself is not weakened, only
  reused as-is against the materialized+worker-selected result.
- `autoresearch/prompts/interpretation.md` and/or a narrower prompt surface for the
  `metric_role_selection` portion of the assessment: the worker-facing contract shrinks to the
  scientific-freedom fields only, replacing the plan to add a fuller `descriptive` explanation to
  the existing full cheat-sheet.
- `autoresearch/schemas/research_quality_assessment.schema.json`: worker-submitted shape narrows;
  final validated shape (post-materialization) is unchanged.
- No change to `B1_WIDTH`/`B2_LOOKBACK`/`A_CONTROL` planning-side materialization
  (`autoresearch-b1-b2-scientific-proposal-v1`) -- this change is interpretation-side only.
- No change to `B3_WIDTH_X_LOOKBACK`/`C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY`, evidence
  plots/renderer, worker profiles, Research Service/Strategy Engine/Market Data Service production
  contracts, or Compact Evidence (explicitly deferred per separate design-explore this session).
- Explicitly out of scope, recorded as follow-up findings from the same audit for a future,
  separate change each: `GateResult` materialization inside `economic_viability`, `experiment`/
  `execution_result` block materialization, `hypothesis`/`market_property_proxy` identity-field
  removal from the worker contract, and partial `TradeoffDimension.assessment` materialization for
  metric-based dimensions.
- Existing regression safety net (`tests/test_autoresearch_quality_policy.py`) is expected to gain
  new coverage for the materializer in the implementation change, but is not modified by this
  proposal itself.
