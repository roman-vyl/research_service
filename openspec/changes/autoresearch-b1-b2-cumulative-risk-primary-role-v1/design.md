## Context

See proposal.md - Why. `scripts/autoresearch_quality_contracts.py` today:
- `STRUCTURAL_PRIMARY_ALLOWED` (:138-149) is the allowlist `validate_metric_roles` checks `primary`
  against for `structural_entry`/`structural_interaction`/`entry_region_selection`.
- `_METRIC_ROLES_FIXED_CORE["structural_entry"|"structural_interaction"]["primary_core"]`
  (:312-321) is the mandatory, worker-uncontrollable core `materialize_metric_roles` always unions
  into `primary`.
- `validate_metric_roles`'s structural branch (:778-795) is one shared `elif` covering all three
  stage kinds; it currently asserts `response_topology` unconditionally and
  `neighborhood_stability`/side-behavior only for `structural_interaction`/`entry_region_selection`.

## Goals / Non-Goals

**Goals:**
- ΣR (aggregate + `long.` + `short.`) becomes part of the mandatory, materialized `primary_core`
  for `structural_entry` and `structural_interaction`, exactly like `response_topology` is today.
- A defense-in-depth mechanical check rejects an assessment missing any of the three ΣR paths from
  `primary`, mirroring the existing `response_topology`/`neighborhood_stability` checks.

**Non-Goals:**
- `entry_region_selection`'s fixed core and validation stay untouched -- it is not named in the
  user's exact requirement, and it shares `STRUCTURAL_PRIMARY_ALLOWED` (which is being widened
  regardless, harmlessly) but not `_METRIC_ROLES_FIXED_CORE`'s per-stage entry.
- No `PromotionThresholds` field, no `GateId`, no numeric ΣR comparison anywhere.
- No new rule requiring every `primary` entry to appear as an `EvidenceRef` -- that would be a new,
  universal enforcement class not applied to any existing primary metric today (including
  `response_topology` itself, which is not even a `CANONICAL_METRIC_PATHS` entry) and is explicitly
  out of scope.

## Decisions

**Scope the new `validate_metric_roles` check to exactly `{"structural_entry",
"structural_interaction"}`, not the shared three-stage `elif` branch's full set.** The branch also
covers `entry_region_selection`, whose fixed core is deliberately left unchanged. Adding an
unconditional "ΣR must be in primary" assertion for all three stage kinds without also adding ΣR to
`entry_region_selection`'s fixed core would make every `entry_region_selection` assessment fail
validation (its materialized `primary` would never contain the new paths). The new checks therefore
gate on `stage in {"structural_entry", "structural_interaction"}` specifically, nested inside (or
alongside) the existing shared branch.

**Require all three paths unconditionally at both stages, not "at least one of."** ΣR is a single
new metric with an aggregate/long/short decomposition, not a member of an equivalence class of
alternative evidence (unlike `CONDITIONAL_ENTRY_EVIDENCE`/`SIDE_BEHAVIOR_EVIDENCE`, which are
worker-selectable alternatives for a qualitative judgment). Placing all three directly in
`primary_core` and asserting all three are present is the literal, minimal reading of "total + long
+ short обязательны".

**`STRUCTURAL_PRIMARY_ALLOWED` widened for all three stage kinds even though only two get the
mandatory core.** This is required regardless: `validate_metric_roles`'s `primary <=
STRUCTURAL_PRIMARY_ALLOWED` check runs for `entry_region_selection` too, and since
`entry_region_selection` inherits the same materialized primary_core as `structural_interaction`
today (unchanged, still `{response_topology, neighborhood_stability}`), widening the allowlist has
no observable effect there -- it only stops being a rejection case if a future change deliberately
adds ΣR to that stage's own fixed core, which this change does not do.

## Risks / Trade-offs

- [Widening `STRUCTURAL_PRIMARY_ALLOWED` without widening `entry_region_selection`'s own fixed core
  could look inconsistent] -> Mitigated: the allowlist is a ceiling (what's permitted), not a floor
  (what's mandatory); `entry_region_selection`'s own mandatory core is unchanged, so its validated
  behavior is unaffected. Documented explicitly in proposal.md and this design so a future reader
  does not mistake this for an oversight.
