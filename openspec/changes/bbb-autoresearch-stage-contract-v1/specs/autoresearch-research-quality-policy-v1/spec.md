## MODIFIED Requirements

### Requirement: Phase A is descriptive control

During `descriptive_baseline`, opportunity frequency, side distribution, hit behavior, execution
and cost facts establish a control. A controlled A→B session MAY define an operator-configured line
of symmetric measurement geometries, with each geometry measured independently on the same naked
starting strategy. Canonical `realised_trade_count` and `win_rate` SHALL be the required compact
reference facts for each geometry. PF, PnL, return, fees, and drawdown MAY be recorded but SHALL NOT
be used as optimization, geometry selection, or early rejection targets. Infrastructure SHALL NOT
derive or require a successful-trade-count fact absent from the canonical evaluator.

#### Scenario: Poor naked-entry PnL does not end structural research

- **WHEN** a naked baseline geometry loses after costs but is sufficiently measured to serve as a
  control
- **THEN** the worker may continue to structural discovery; infrastructure does not reject the
  research program because of baseline profitability.

#### Scenario: Configured reference line is not exit optimization

- **WHEN** Phase A measures configured symmetric geometries such as 2/2, 3/3, and 4/4
- **THEN** each geometry retains its trade count and win rate as a separate reference and neither
  worker nor supervisor declares the geometry with the highest win rate, PF, or PnL a winner.

### Requirement: Phase B prioritizes conditional entry quality

During `structural_entry` and `structural_interaction`, each experiment SHALL use one fixed neutral
symmetric geometry matched exactly to a completed naked Phase A reference. Comparisons SHALL be
geometry-to-geometry and SHALL NOT compare a filtered result at one exit geometry with a baseline
at another. Primary evidence SHALL be win/hit-rate uplift against that matched baseline, side hit
behavior, response shape, neighborhood stability, realised trade count, and
thinning/concentration. PF, gross/net/return, fees, and drawdown SHALL be secondary sanity evidence
and SHALL NOT dominate interpretation. The set of configured geometries is a measurement reference
line, not an exit-optimization search space.

#### Scenario: Win-rate uplift is not a scalar leaderboard

- **WHEN** one Phase-B filter has the highest win rate but obtains it through severe thinning or an
  unstable neighborhood
- **THEN** it is not automatically preferred and may be blocked as structurally unsupported.

#### Scenario: Phase-C criteria are not applied early

- **WHEN** a Phase-B experiment has not yet fixed a stable entry region
- **THEN** exit-geometry profitability criteria are not applied to prune its topology evidence.

#### Scenario: Geometry-to-geometry comparison

- **WHEN** a filtered B result uses the Phase A geometry identified as A-3
- **THEN** its uplift, retained sample, topology, and side behavior are assessed only against the
  naked A-3 reference, not against A-2, A-4, or an aggregate best geometry.
