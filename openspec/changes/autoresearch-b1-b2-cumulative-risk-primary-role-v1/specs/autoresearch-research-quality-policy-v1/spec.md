## MODIFIED Requirements

### Requirement: Phase B prioritizes conditional entry quality

During `structural_entry` and `structural_interaction` under one fixed neutral symmetric exit,
primary evidence SHALL be win/hit-rate uplift against baseline, side hit behavior, response shape,
neighborhood stability, realised trade count, thinning/concentration, and the cumulative risk
outcome (ΣR) of the candidate -- aggregate, `long`, and `short` -- all three mandatory and fixed,
never left to worker selection. Side ΣR decomposition (`long.cumulative_risk_outcome`,
`short.cumulative_risk_outcome`) is mandatory already at `structural_entry`, not deferred to
`structural_interaction`. PF, gross/net/return, fees, and drawdown SHALL be secondary sanity
evidence and SHALL NOT dominate interpretation. Naming ΣR as mandatory primary evidence is a formal
epistemic-checklist requirement, not a citation-count guarantee -- it does not require every primary
metric to individually appear in an `EvidenceRef`, and it introduces no promotion gate, threshold,
or scalar ranking on ΣR.

#### Scenario: Win-rate uplift is not a scalar leaderboard

- **WHEN** one Phase-B filter has the highest win rate but obtains it through severe thinning or an
  unstable neighborhood
- **THEN** it is not automatically preferred and may be blocked as structurally unsupported.

#### Scenario: Phase-C criteria are not applied early

- **WHEN** a Phase-B experiment has not yet fixed a stable entry region
- **THEN** exit-geometry profitability criteria are not applied to prune its topology evidence.

#### Scenario: cumulative_risk_outcome is mandatory primary evidence at structural_entry

- **WHEN** a `structural_entry` (B1) `research_quality_assessment` is validated
- **THEN** its `stage.metric_roles.primary` MUST include `cumulative_risk_outcome`,
  `long.cumulative_risk_outcome`, and `short.cumulative_risk_outcome`; an assessment missing any of
  the three is rejected.

#### Scenario: cumulative_risk_outcome is mandatory primary evidence at structural_interaction

- **WHEN** a `structural_interaction` (B2) `research_quality_assessment` is validated
- **THEN** its `stage.metric_roles.primary` MUST include `cumulative_risk_outcome`,
  `long.cumulative_risk_outcome`, and `short.cumulative_risk_outcome`, in addition to the existing
  `response_topology`/`neighborhood_stability`/side-behavior requirements; an assessment missing any
  of the three is rejected.

#### Scenario: ΣR primary role is not a leaderboard or a citation mandate

- **WHEN** ΣR is present in `stage.metric_roles.primary` for a `structural_entry`/
  `structural_interaction` assessment
- **THEN** this alone neither ranks candidates by ΣR nor requires an `EvidenceRef` citing
  `cumulative_risk_outcome` to exist anywhere in the assessment -- consistent with how
  `response_topology`/`neighborhood_stability` already function as formal primary-role names today.
