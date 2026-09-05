## ADDED Requirements

### Requirement: Deterministic tradeoff-relation materialization

The interpretation worker SHALL author only the per-dimension `assessment` and `evidence_refs` for
each tradeoff comparison; the comparison's overall `relation` SHALL be materialized deterministically
by the supervisor from those `assessment` values, not authored by the worker. The existing
Pareto-consistency validator SHALL continue to enforce the complete, materialized comparison
unchanged, as an independent post-hoc defense.

#### Scenario: Worker submits no relation

- **WHEN** the interpretation worker submits a tradeoff comparison
- **THEN** the submission contains `left_subject_ref`, `right_subject_ref`, `stage_kind`, and
  `dimensions` only; a submission containing `relation` is rejected before materialization.

#### Scenario: Materialized relation passes independent validation

- **WHEN** the supervisor computes `relation` from the worker's `dimensions[].assessment` values and
  compiles the complete comparison
- **THEN** the existing `relation_is_pareto_consistent` check evaluates that complete comparison
  exactly as it would a fully worker-authored one, unchanged.

### Requirement: Tradeoff comparison subjects are scoped to the current iteration

A tradeoff comparison's `left_subject_ref` and `right_subject_ref` SHALL refer only to candidates
completed within the current iteration's own batch, or the current iteration's
`promotion_subject.region_id`. A comparison against a prior iteration's baseline (such as the frozen
`A_CONTROL` reference) SHALL be reported via `structural_promise.baseline_comparison`, not as a
`tradeoff_summary` comparison.

#### Scenario: Worker is told the correct field for a baseline comparison

- **WHEN** the interpretation worker reads the tradeoff-summary guidance in its prompt
- **THEN** the guidance states that comparison subjects must come from the current iteration's own
  batch (or region), and directs a comparison against a historical baseline to
  `structural_promise.baseline_comparison` instead.
