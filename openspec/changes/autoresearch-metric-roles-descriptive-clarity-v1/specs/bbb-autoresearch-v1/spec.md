## ADDED Requirements

### Requirement: Deterministic metric-role materialization

For every stage kind, the interpretation worker SHALL author only the `metric_roles` selections
that carry genuine evidentiary judgment for that stage kind; every role assignment that is fully or
mostly determined by the active stage's fixed quality policy SHALL be materialized deterministically
by the supervisor from that stage's policy constants, not authored by the worker. The existing
mechanical validator SHALL continue to enforce the complete, materialized `metric_roles` object
unchanged, as an independent post-hoc defense.

#### Scenario: Descriptive-baseline stage requires no worker metric-role input

- **WHEN** the active stage kind is `descriptive_baseline`
- **THEN** the supervisor materializes the complete `metric_roles` object (`primary`, `secondary`,
  `descriptive`, `promotion_gates`) from the stage's fixed policy, and the worker is not required to
  submit any `metric_roles` content for this stage.

#### Scenario: Structural stages retain only the genuine evidentiary choice

- **WHEN** the active stage kind is `structural_entry`, `structural_interaction`, or
  `entry_region_selection`
- **THEN** the worker submits only which specific named evidence to include from each "at least one
  of" requirement (conditional-entry evidence, sample/thinning evidence, and side-behavior evidence
  where applicable) and, if relevant, which additional promotion gates apply this iteration; the
  supervisor materializes the mandatory core, `secondary`, and `descriptive` deterministically and
  compiles the complete `metric_roles` object before validation.

#### Scenario: Exit-geometry and robustness-validation stages retain only genuinely optional choices

- **WHEN** the active stage kind is `exit_geometry` or `robustness_validation`
- **THEN** the worker submits only the genuinely optional selections for that stage (additional
  promotion gates for `exit_geometry`; additional optional primary evidence and promotion gates for
  `robustness_validation`); every mandatory or fixed role assignment is materialized by the
  supervisor, never authored by the worker.

#### Scenario: Materialized metric_roles still passes independent validation

- **WHEN** the supervisor compiles a complete `metric_roles` object from the worker's narrow
  selection and the stage's deterministic core
- **THEN** the existing mechanical validator (`validate_metric_roles`) evaluates that complete
  object exactly as it would a fully worker-authored one, unchanged, and rejects it if it is
  invalid.
