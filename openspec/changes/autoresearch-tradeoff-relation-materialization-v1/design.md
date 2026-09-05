## Context

See `proposal.md` - Why. Two independently-confirmed root causes inside the same narrow
`tradeoff_summary` contract area, requiring two independent, narrow fixes -- one mechanical
(materialization, mirroring the `metric_role_selection` precedent), one prompt-only (subject-ref
scope clarity). Neither touches `enforce_quality_policy`'s broader logic, `EvidenceRef`, or any
other interpretation field.

## Goals / Non-Goals

**Goals:**
- The worker never authors `tradeoff_summary.comparisons[].relation`; the supervisor materializes
  it deterministically and the unchanged `relation_is_pareto_consistent` still enforces the result.
- The worker-facing prompt explicitly states the current-iteration scope of
  `left_subject_ref`/`right_subject_ref` and points to `structural_promise.baseline_comparison` for
  vs-baseline comparisons.
- Worker-facing schema/prompt and the actual worker contract match exactly -- no new
  schema-vs-prompt discrepancy left unaddressed (the schema still shows `relation` since
  `TradeoffComparison` itself is unchanged; the prompt gets an explicit exception, mirroring the
  existing `range_authority_note`/`metric_role_selection` precedents for this exact class of
  conflict).

**Non-Goals:**
- No change to `enforce_quality_policy`'s `subject_refs`/`candidate_facts` scope -- confirmed a
  separate, narrower fix (prompt guidance) is correct and sufficient; widening `candidate_facts` to
  include prior-iteration candidates would require loading a different iteration's batch artifact,
  a materially larger change outside this narrow blocker.
- No change to `TradeoffDimension`, `EvidenceRef`, `metric_roles`/`metric_role_selection`, or any
  other `research_quality_assessment` field.
- No fix to the `TradeoffComparison.relation_is_pareto_consistent` validator's own logic -- reused
  completely unchanged.
- No general interpretation-contract refactor.

## Decisions

**`derive_tradeoff_relation` encodes the exact same total mapping `relation_is_pareto_consistent`
already checks, so materialized output always passes it.** Given `values = {assessment for each
dimension}`:

```
if values == {"equivalent"}:             relation = "equivalent"
elif "left_better" in values and "right_better" in values:
                                          relation = "tradeoff"
elif "left_better" in values and "uncertain" not in values:
                                          relation = "left_dominates"
elif "right_better" in values and "uncertain" not in values:
                                          relation = "right_dominates"
else:                                     relation = "incomparable"
```

This is a total function (always produces exactly one of the five valid `relation` values for any
non-empty `dimensions` list) and was checked by hand against every branch of
`relation_is_pareto_consistent` (`scripts/autoresearch_quality_contracts.py:581-599`) -- e.g.
`{"left_better", "uncertain"}` (no `right_better`) correctly falls through to `"incomparable"`,
since it satisfies neither `left_dominates` (blocked by `uncertain`) nor `tradeoff` (needs both
`left_better` and `right_better`). Alternative considered: let the materializer raise its own error
for "ambiguous" cases instead of defaulting to `incomparable` -- rejected, since `incomparable` has
no positive constraint in the validator (always valid) and correctly represents "the evidence
doesn't cleanly support a stronger claim," which is itself often the honest, worker-intended answer
when it names an `uncertain` dimension without both-sided better evidence.

**Worker submits `TradeoffComparisonSelection` (new `ExactModel`, no `relation` field), not a
partial `TradeoffComparison`.** Same pattern as `MetricRoleSelection`: `ExactModel`'s
`extra="forbid"` means a worker submission that still includes `relation` is rejected automatically
during `TradeoffComparisonSelection.model_validate()` -- no separate manual check needed.

**Materialization happens in `validate_iteration_result`, in the same try block as the existing
`metric_role_selection` -> `metric_roles` step**, before `validate_assessment()`. For each raw
comparison dict in `raw_assessment["tradeoff_summary"]["comparisons"]`: parse as
`TradeoffComparisonSelection`, compute `relation` via `derive_tradeoff_relation`, inject it into the
raw dict, then proceed. This mutates the same `result` dict object already reused downstream by
`_advance_state`/journal writing (confirmed by the existing `metric_role_selection` precedent's own
verification) -- no additional disk round-trip concern.

**Root cause 2 fix is prompt-only, not a schema/mechanics change.** `structural_promise.baseline_comparison`
(`scripts/autoresearch_quality_contracts.py:447`) already exists and was correctly populated by the
worker in the failing smoke (`"improved"`) -- the worker independently, redundantly, and incorrectly
also tried to formalize the same comparison as a `TradeoffComparison` naming a prior-iteration
candidate as a subject, which the current-iteration-scoped `subject_refs` check correctly rejects.
Confirmed this is a narrow prompt-clarity gap (`interpretation.md` never explains the scope
constraint or points to the existing correct field), not a case for widening the mechanical check.

## Risks / Trade-offs

- [`derive_tradeoff_relation`'s `incomparable` fallback masks a case the worker intended as something
  more specific] → Mitigation: `incomparable` is itself a legitimate, meaningful relation value in
  the existing schema (not an error state) for exactly the "insufficient/mixed-without-clear-tradeoff
  evidence" case; a worker that wants a stronger claim (`tradeoff`/`left_dominates`/etc.) must submit
  `dimensions[].assessment` values that actually support it -- the materializer does not invent
  support that isn't in the worker's own evidence.
- [Prompt-only fix for root cause 2 doesn't prevent a differently-worded but equally invalid
  cross-iteration comparison attempt] → Mitigation: the existing mechanical `subject_refs` check
  remains fail-closed regardless of prompt wording -- worst case is a clear, already-correct error
  message (`"tradeoff comparison references an unknown candidate or region"`), not silent
  acceptance; the prompt fix only reduces how often a capable worker hits it needlessly.

## Migration Plan

Additive/tightening, no `research_quality_assessment.schema.json` version bump: the final,
materialized `TradeoffComparison` object has the exact same shape as today. Only the worker-facing
input narrows (no `relation`) and the prompt gains guidance. No stored artifact needs migration --
only affects interpretation calls made after this change ships.

## Open Questions

None -- both root causes were investigated to a concrete, implementable conclusion; no
implementation-time ambiguity remains for this narrow scope.
