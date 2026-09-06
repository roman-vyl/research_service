## Why

`cumulative_risk_outcome` (ΣR, aggregate/`long.`/`short.`) is already physically computed and
persisted (`BatchCandidateResult`/`BatchSideSummary`, `summary.json`, `execution_output.json`) and
already citable (`CANONICAL_METRIC_PATHS`). It is not yet a formal part of the `structural_entry`/
`structural_interaction` primary-evidence checklist, so a worker has no standing requirement to
treat it as a mandatory structural signal alongside `response_topology`/`neighborhood_stability`.

## What Changes

- `STRUCTURAL_PRIMARY_ALLOWED` gains `cumulative_risk_outcome`, `long.cumulative_risk_outcome`,
  `short.cumulative_risk_outcome`.
- `_METRIC_ROLES_FIXED_CORE["structural_entry"]["primary_core"]` gains `cumulative_risk_outcome`,
  `long.cumulative_risk_outcome`, `short.cumulative_risk_outcome` (alongside the existing
  `response_topology`) -- side decomposition is mandatory already at B1, not deferred to B2.
- `_METRIC_ROLES_FIXED_CORE["structural_interaction"]["primary_core"]` gains the same three paths
  (alongside the existing `response_topology`, `neighborhood_stability`).
- `validate_metric_roles()` gains defense-in-depth checks in the structural branch: reject a
  `structural_entry` or `structural_interaction` assessment whose `primary` is missing
  `cumulative_risk_outcome`, `long.cumulative_risk_outcome`, or `short.cumulative_risk_outcome`.
  `entry_region_selection`'s fixed core is untouched by this change (not named in the exact
  requirement), so the new check does not apply to it -- adding it there without also touching its
  fixed core would make every `entry_region_selection` assessment fail validation.

No change to prompts, `program.md`, gates, `PromotionThresholds`, dense sweep, Compact Evidence,
Strategy Engine, or Research Service. No new promotion gate, no ΣR threshold, no citation-count
enforcement (a primary-role entry remains a formal epistemic checklist item, not a guarantee that
every primary metric is individually cited via `EvidenceRef` -- unchanged from today).

## Capabilities

### Modified Capabilities
- `autoresearch-research-quality-policy-v1`: "Phase B prioritizes conditional entry quality" gains
  `cumulative_risk_outcome` (aggregate and per-side) as mandatory primary evidence for
  `structural_entry` and `structural_interaction`, without altering win-rate/PF/thinning/side-
  behavior's existing roles or the non-leaderboard scenarios already specified there.

## Impact

- `scripts/autoresearch_quality_contracts.py`: `STRUCTURAL_PRIMARY_ALLOWED`,
  `_METRIC_ROLES_FIXED_CORE`, `validate_metric_roles()`.
- `entry_region_selection`'s fixed core and validation are untouched by this change (not named in
  the exact requirement).
