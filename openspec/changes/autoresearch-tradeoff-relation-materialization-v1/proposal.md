## Why

Controlled HOST smoke `ema-anchor-sonnet-metricroles-smoke-20260905202722` (`claude-sonnet46`)
confirmed the `metric_roles` fix works, then hit a new, real blocker: `B1_WIDTH` interpretation
failed 3/3 attempts, all inside `research_quality_assessment.tradeoff_summary`, not `metric_roles`.

**Root cause 1 (2 of 3 attempts, identical): `TradeoffComparison.relation_is_pareto_consistent`
rejects a worker-declared `relation` that contradicts the worker's own `dimensions[].assessment`.**
The worker's actual submitted content (`var/autoresearch/.../iterations/0002/iteration_result.json`)
shows exactly the failure: dimensions `[profitability: left_better, risk: left_better,
sample_size: right_better, side_breadth: left_better, neighborhood_stability: uncertain]` with
`relation: "left_dominates"` -- but `right_better` is present, which `left_dominates` forbids. The
worker's own `rationale` text even says so directly: "left dominates on profitability, risk, and
side breadth **at the cost of sample size**" -- that is the definition of `"tradeoff"`, not
`"left_dominates"`. **`relation` is fully and deterministically derivable from
`dimensions[].assessment`** -- `relation_is_pareto_consistent`
(`scripts/autoresearch_quality_contracts.py:581-599`) already encodes the exact total mapping;
nothing about which `relation` value is correct is a judgment call once the per-dimension
`assessment` values are fixed. Per the standing principle already applied to `metric_roles`
(`autoresearch-metric-roles-descriptive-clarity-v1`, archived): the worker should not be asked to
manually reproduce a value the harness can compute exactly.

**Root cause 2 (1 of 3 attempts, different symptom, different code path):
`"tradeoff comparison references an unknown candidate or region"`
(`scripts/autoresearch_quality_contracts.py:895-905`).** Investigated separately, confirmed NOT the
same root cause. `enforce_quality_policy`'s `subject_refs` is scoped to the current iteration's own
completed candidates (`candidate_facts`) plus `promotion_subject.region_id` -- it has no
information about candidates from a prior iteration's own batch (e.g. `A_CONTROL`'s `"a-control"`).
The worker (same failing attempt) tried to build a formal `TradeoffComparison` with
`right_subject_ref: "a-control"` to express "width=10 dominates control" -- but the same assessment
**already correctly reports this exact comparison** via the dedicated, existing field
`structural_promise.baseline_comparison: "improved"` (`scripts/autoresearch_quality_contracts.py:447`).
There is no schema-level guidance anywhere telling the worker that (a) `tradeoff_summary` subject
refs are scoped to the current batch only, or (b) a vs-control comparison already has a correct,
dedicated home. `autoresearch/prompts/interpretation.md` mentions `tradeoff_summary.comparisons`
exactly once, only as a field-name example inside the generic "read the schema exactly" sentence --
zero actual guidance on subject-ref scope or `relation` semantics. This is a prompt-clarity gap in
the same narrow `tradeoff_summary` contract area, not a mechanical defect -- fixed by prompt
guidance only, no code/schema change to `enforce_quality_policy` or `subject_refs`.

## What Changes

- A new narrow worker-input model (`TradeoffComparisonSelection`) drops `relation` from what the
  worker submits for each comparison -- only `left_subject_ref`, `right_subject_ref`, `stage_kind`,
  `dimensions` (each with `assessment` + `evidence_refs`, unchanged). Pydantic's existing
  `extra="forbid"` (`ExactModel`) rejects a submission that still includes `relation`, with no new
  manual check needed.
- A new deterministic function derives the correct `relation` from `dimensions[].assessment`,
  encoding the exact same total mapping `relation_is_pareto_consistent` already checks (so
  materialized output always passes that unchanged validator).
- The materialization is wired into `scripts/autoresearch_supervisor.py`'s
  `validate_iteration_result`, in the same place and pattern as the existing `metric_role_selection`
  materialization: parse the worker's narrow selection, compute `relation`, inject it, then run the
  unchanged `validate_assessment()`/`relation_is_pareto_consistent()` as independent post-hoc
  defense -- no weakening.
- `autoresearch/prompts/interpretation.md` gains: (a) an explicit exception to its existing "the
  schema wins" rule for `tradeoff_summary.comparisons[].relation` (the schema still shows it,
  materialized by the supervisor, not worker-authored -- same pattern as the `metric_role_selection`
  exception added for the prior fix), (b) explicit guidance that `left_subject_ref`/
  `right_subject_ref` must both be candidates from the current iteration's own batch (or the
  current `promotion_subject.region_id`), and that a comparison against a historical baseline (like
  `A_CONTROL`) belongs in `structural_promise.baseline_comparison`, not `tradeoff_summary`.
- No change to `enforce_quality_policy`'s `subject_refs` scope, `candidate_facts`, or any other
  interpretation field -- root cause 2 is a prompt-only fix, confirmed narrow to this contract area.
- No change to `MetricRoles`/`metric_role_selection` (already fixed, separately verified).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `bbb-autoresearch-v1`: the interpretation worker is no longer required to author
  `tradeoff_summary.comparisons[].relation` -- a value fully determined by the worker's own
  `dimensions[].assessment` -- and the worker-facing contract explicitly scopes tradeoff comparison
  subjects to the current iteration's own candidates/region, directing vs-baseline comparisons to
  the existing `structural_promise.baseline_comparison` field instead.

## Impact

- `scripts/autoresearch_quality_contracts.py`: new `TradeoffComparisonSelection` model and
  `derive_tradeoff_relation()` function; `TradeoffComparison`/`relation_is_pareto_consistent`
  unchanged, reused as-is.
- `scripts/autoresearch_supervisor.py`: `validate_iteration_result` gains the tradeoff-relation
  materialization step, alongside the existing `metric_role_selection` materialization.
- `autoresearch/prompts/interpretation.md`: adds the schema exception + subject-ref scope guidance
  described above.
- No change to `B1_WIDTH`/`B2_LOOKBACK`/`A_CONTROL` planning-side materialization, `B3`/`C`/`D`
  stages, evidence plots/renderer, worker profiles, or RS/SE/MDS production contracts.
- No change to `metric_roles`/`metric_role_selection` (`autoresearch-metric-roles-descriptive-clarity-v1`,
  already implemented and verified, not yet archived).
- Existing regression safety net (`tests/test_autoresearch_quality_policy.py`) is expected to gain
  new coverage in the implementation change, but is not modified by this proposal itself.
