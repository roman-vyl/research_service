## 1. Allowlist and fixed cores

- [x] 1.1 Add `"cumulative_risk_outcome"`, `"long.cumulative_risk_outcome"`,
      `"short.cumulative_risk_outcome"` to `STRUCTURAL_PRIMARY_ALLOWED`
      (`scripts/autoresearch_quality_contracts.py:138-149`).
- [x] 1.2 Add the same three paths to `_METRIC_ROLES_FIXED_CORE["structural_entry"]["primary_core"]`
      (:312-316), alongside the existing `response_topology`.
- [x] 1.3 Add the same three paths to
      `_METRIC_ROLES_FIXED_CORE["structural_interaction"]["primary_core"]` (:317-321), alongside the
      existing `response_topology`/`neighborhood_stability`. Do not touch
      `entry_region_selection`'s entry.

## 2. Defense-in-depth validation

- [x] 2.1 In `validate_metric_roles()`'s structural branch (:778-795), add a check scoped to
      `stage in {"structural_entry", "structural_interaction"}` (not the full three-stage set)
      rejecting an assessment whose `primary` is missing `cumulative_risk_outcome`,
      `long.cumulative_risk_outcome`, or `short.cumulative_risk_outcome`.

## 3. Tests

- [x] 3.1 `materialize_metric_roles("structural_entry", MetricRoleSelection())`'s `primary` includes
      `response_topology`, `cumulative_risk_outcome`, `long.cumulative_risk_outcome`,
      `short.cumulative_risk_outcome`.
- [x] 3.2 `materialize_metric_roles("structural_interaction", MetricRoleSelection())`'s `primary`
      includes `response_topology`, `neighborhood_stability`, `cumulative_risk_outcome`,
      `long.cumulative_risk_outcome`, `short.cumulative_risk_outcome`.
- [x] 3.3 `validate_metric_roles` rejects a `structural_entry`/`structural_interaction` assessment
      whose `primary` is missing `cumulative_risk_outcome` (aggregate absent, long/short present).
- [x] 3.4 `validate_metric_roles` rejects when `long.cumulative_risk_outcome` is missing (aggregate
      and short present).
- [x] 3.5 `validate_metric_roles` rejects when `short.cumulative_risk_outcome` is missing (aggregate
      and long present).
- [x] 3.6 Confirm `_METRIC_ROLES_FIXED_CORE["structural_entry"|"structural_interaction"]["secondary"]`
      is unchanged (`net_pnl`, `return_pct`, `profit_factor`, `max_drawdown`) -- PF/PnL did not move
      into `primary`.
- [x] 3.7 Confirm `entry_region_selection`'s materialized `primary` is unchanged (still exactly
      `response_topology`, `neighborhood_stability`) and that `validate_metric_roles` still accepts
      it without the new ΣR paths.
- [x] 3.8 Full repo test suite: 473 passed, 0 failed (up from 463 baseline; +10 new tests, including
      a positive sanity check that a fully valid structural materialization still passes).

## 4. Verification

- [x] 4.1 `openspec validate --strict --changes autoresearch-b1-b2-cumulative-risk-primary-role-v1`
      passes (10/10 changes, 0 failed).
- [x] 4.2 `git diff --check` clean (no whitespace errors).
