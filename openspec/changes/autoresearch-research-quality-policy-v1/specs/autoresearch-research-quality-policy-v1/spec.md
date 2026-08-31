# AutoResearch Research Quality Policy v1 Specification

## Purpose

Define stage-aware, multi-objective research-quality and promotion semantics above BBB AutoResearch
v1 without changing the canonical evaluator or creating a scalar optimizer.

## ADDED Requirements

### Requirement: Experiment success and strategy success are independent

The system SHALL represent operational completion, information value, and region promotion as
separate states. A completed experiment SHALL NOT imply a successful strategy, and an economically
losing experiment SHALL NOT be classified as a failed research result solely because it loses.

#### Scenario: Losing but topology-informative sweep is retained

- **WHEN** a completed sweep is after-cost losing but maps a stable threshold, plateau, monotonic,
  flat, U-shaped, boundary-running, or hypothesis-rejecting response
- **THEN** its information assessment may be `informative`, its evidence and negative economics are
  retained, and it is not discarded as a failed experiment.

### Requirement: Four-layer quality assessment

Every quality-aware iteration SHALL explicitly and independently assess information value,
structural promise, economic viability, and robustness. Not-yet-applicable or untested layers SHALL
use explicit states rather than fabricated positive or negative conclusions.

#### Scenario: Early discovery has no economic verdict

- **WHEN** a structural discovery iteration has not reached entry-region promotion
- **THEN** economic viability and robustness may be `not_applicable`, while information and
  structural assessments remain complete.

### Requirement: Information value has no profitability hard gate

Information value SHALL describe whether the experiment distinguishes hypotheses or maps response
behavior. Recognized valuable outcomes SHALL include flat, monotonic, threshold, plateau/broad
optimum, isolated spike, boundary-running, U/inverted-U, side asymmetry, thinning,
temporal/regime concentration, and hypothesis rejection. Profitability SHALL NOT be a hard gate for
this layer.

#### Scenario: Negative hypothesis result increases knowledge

- **WHEN** a comparable experiment rejects its hypothesis with meaningful evidence
- **THEN** the result may be `informative` and SHALL remain durable even when no region is promoted.

### Requirement: Structural promise is region- and explanation-aware

Structural promise SHALL consider appropriate-baseline change, response topology, neighborhood
stability, sample adequacy, trade-count thinning, long/short behavior, economic direction, plausible
market-state interpretation, and a competing explanation. It SHALL NOT require final profitability
during structural discovery.

#### Scenario: Profitable isolated spike is not promoted

- **WHEN** one profitable point is surrounded by materially unsupported neighbors
- **THEN** it SHALL NOT be `eligible_for_next_stage`, regardless of its PF, PnL, return, win rate,
  or drawdown.

#### Scenario: Lower PF broad region remains investigable

- **WHEN** a lower-PF region has broad stable topology, meaningful sample, and no disqualifying
  stage-appropriate evidence while a higher-PF point is narrow or unstable
- **THEN** the broad region may remain `investigate_region`; infrastructure SHALL NOT prune it in
  favor of the higher-PF point.

### Requirement: Positive after-cost economics gates final entry promotion

A region carried from stable entry selection into exit research, or promoted in any later economic
stage, SHALL be positive after costs on its representative canonical candidates. Positive after-cost
economics requires positive `net_pnl` and `return_pct`, consistency with `gross_pnl - fees_paid`,
and directionally consistent PF when PF is non-null. This invariant SHALL NOT be applied as a
Phase-A or Phase-B pruning rule.

#### Scenario: After-cost negative final region cannot pass

- **WHEN** a proposed final entry region has zero or negative canonical net PnL/return after fees
- **THEN** its economic viability is `not_viable` and it cannot be `eligible_for_next_stage`, even
  if another isolated metric is favorable.

#### Scenario: Near-zero Phase-B economics does not erase entry-quality evidence

- **WHEN** a neutral symmetric-exit structural sweep shows stable conditional entry-quality uplift
  but net PnL is near zero
- **THEN** the structural finding remains assessable and is not rejected by the later-stage
  after-cost promotion gate.

### Requirement: Economic facts are mutually consistent

Economic viability SHALL use the existing canonical metric meanings. The supervisor SHALL reject a
promotion claim whose referenced PF, net result/return, gross result, and fees are mutually
inconsistent, without recalculating trading metrics.

#### Scenario: PF contradicts positive-net claim

- **WHEN** a promotion assessment claims positive after-cost economics but referenced non-null PF
  and net/return signs contradict that claim
- **THEN** the promotion claim is rejected as contract/evidence inconsistent.

### Requirement: Configured thresholds are explicit and nullable

The resolved session policy SHALL carry explicit nullable promotion thresholds for realised trade
count, PF, after-cost return, trade-close drawdown magnitude, long/short trade count, and relative
trade-count reduction. No arbitrary numeric default SHALL be supplied by infrastructure.

#### Scenario: Configured minimum trade count is enforced

- **WHEN** `minimum_realised_trade_count` is configured and a representative promotion candidate is
  below it
- **THEN** the supervisor mechanically records a failed gate and rejects the promotion claim.

#### Scenario: Absent optional threshold invents no gate

- **WHEN** an optional threshold is null
- **THEN** the supervisor neither supplies a default nor fails a result for that absent threshold;
  qualitative stage requirements still apply.

### Requirement: Robustness controls strong promotion

Robustness assessment SHALL cover neighborhood stability, parameter perturbation, meaningful sample,
thinning, temporal concentration, regime concentration, aggregate/long/short behavior, and
holdout/alternate window or ticker evidence when available and methodologically justified. Required
validation failure SHALL block or demote promotion.

#### Scenario: Neighboring instability blocks promotion

- **WHEN** a region's representative economics are favorable but nearby parameter perturbations fail
- **THEN** the region is not eligible for strong promotion and carries a neighborhood-stability
  blocker.

#### Scenario: Validation failure demotes a region

- **WHEN** a previously promising region fails a required holdout, temporal, regime, side, or
  perturbation validation
- **THEN** it is `demoted_after_validation` or rejected, and the failed evidence remains durable.

### Requirement: Long/short behavior has explicit scope

Every applicable assessment SHALL classify side behavior as `two_sided_consistent`,
`long_dominant`, `short_dominant`, `regime_specific_directional`,
`aggregate_masks_side_failure`, or `mixed_unresolved`. One-sided behavior SHALL NOT be rejected
solely for lacking symmetry, but SHALL have a narrower claim and require additional
temporal/regime validation before strong promotion.

#### Scenario: Aggregate profitable and short losing is directional

- **WHEN** aggregate economics are positive but the short side loses and the long side explains the
  result
- **THEN** the finding is classified as long-dominant, directional, or aggregate-masking-side-
  failure as evidence warrants; it is not classified as universal/two-sided.

#### Scenario: Consistent two-sided behavior supports broader scope

- **WHEN** long and short both show consistent supported behavior with meaningful samples
- **THEN** `two_sided_consistent` is positive evidence toward broader applicability, but robustness
  requirements still apply before a universal conclusion.

### Requirement: Multi-metric comparison is Pareto-like and non-ranking

Trade-off assessment SHALL represent profitability, absolute after-cost result, risk, sample size,
side breadth, and neighborhood stability separately. Domination requires no worse evidence on every
applicable dimension, strictly better evidence on at least one, a comparable market universe/stage,
and no uncertain required dimension. Mixed advantages SHALL be a trade-off, not a winner.

#### Scenario: Higher PF with collapsing trade count is not automatically preferred

- **WHEN** candidate A has higher PF but a sharply smaller trade sample than candidate B
- **THEN** A does not dominate B solely because of PF and the worker receives an explicit
  profitability-versus-sample trade-off.

#### Scenario: Supervisor never chooses numeric winner

- **WHEN** multiple candidates or regions expose different PF/PnL/drawdown/sample/side trade-offs
- **THEN** the supervisor validates and persists the comparison but does not rank, keep, discard, or
  select a winner.

### Requirement: Phase binding is explicit without replacing flexible phases

Each configured phase string SHALL bind to exactly one stage kind: `descriptive_baseline`,
`structural_entry`, `structural_interaction`, `entry_region_selection`, `exit_geometry`, or
`robustness_validation`. The supervisor SHALL enforce assessment requirements for the bound stage
but SHALL NOT choose the next phase.

#### Scenario: Unknown phase binding fails closed

- **WHEN** an iteration reports a phase absent from the resolved policy or with conflicting bindings
- **THEN** the supervisor rejects the assessment as ambiguous rather than guessing metric roles.

### Requirement: Phase A is descriptive control

During `descriptive_baseline`, opportunity frequency, side distribution, hit behavior, execution and
cost facts establish a control. PF, PnL, return, and drawdown MAY be recorded but SHALL NOT be used
as optimization or early rejection targets.

#### Scenario: Poor naked-entry PnL does not end structural research

- **WHEN** the naked baseline loses after costs but is sufficiently measured to serve as a control
- **THEN** the worker may continue to structural discovery; infrastructure does not reject the
  research program because of baseline profitability.

### Requirement: Phase B prioritizes conditional entry quality

During `structural_entry` and `structural_interaction` under one fixed neutral symmetric exit,
primary evidence SHALL be win/hit-rate uplift against baseline, side hit behavior, response shape,
neighborhood stability, realised trade count, and thinning/concentration. PF, gross/net/return,
fees, and drawdown SHALL be secondary sanity evidence and SHALL NOT dominate interpretation.

#### Scenario: Win-rate uplift is not a scalar leaderboard

- **WHEN** one Phase-B filter has the highest win rate but obtains it through severe thinning or an
  unstable neighborhood
- **THEN** it is not automatically preferred and may be blocked as structurally unsupported.

#### Scenario: Phase-C criteria are not applied early

- **WHEN** a Phase-B experiment has not yet fixed a stable entry region
- **THEN** exit-geometry profitability criteria are not applied to prune its topology evidence.

### Requirement: Exit geometry makes economics primary

During `exit_geometry`, the structural entry region SHALL remain fixed and primary evidence SHALL
shift to after-cost net result/return, PF, trade-close drawdown, realistic payoff geometry, trade
count, side profitability, and neighboring exit-parameter stability.

#### Scenario: Symmetric discovery economics are not final economics

- **WHEN** Phase-C asymmetric payoff geometry is evaluated
- **THEN** its economic evidence is assessed separately from Phase-B's neutral symmetric
  measurement and may not be inferred from it.

### Requirement: Durable quality representation is versioned

The resolved quality policy, full per-iteration assessment, stage-specific metric roles, side class,
trade-offs, promotion decision, and blockers SHALL be durable. Exact current v1 enclosing schemas
SHALL NOT be silently expanded; implementation SHALL use explicit new AutoResearch contract
versions and preserve v1 document identity.

#### Scenario: Restart preserves quality meaning

- **WHEN** a quality-aware session restarts
- **THEN** it recovers the same immutable policy, active stage binding, latest assessment, promotion
  history, and evidence references without relying on chat history.

### Requirement: Supervisor, worker, and evaluator responsibilities remain separate

The supervisor SHALL perform exact contract validation, evidence-reference checks, configured gate
enforcement, and mechanical persistence. The worker SHALL interpret topology, trade-offs, side
scope, competing explanations, and next information gain. The existing Research evaluator SHALL
only produce canonical facts and remain unchanged.

#### Scenario: Semantic interpretation is not reconstructed by infrastructure

- **WHEN** a worker reports topology, directional scope, or a competing explanation
- **THEN** the supervisor validates the required shape/evidence and persists it without deriving a
  replacement interpretation from metrics.

### Requirement: No stable edge is a valid terminal conclusion

`no_stable_edge` SHALL remain a valid evidence-backed terminal promotion disposition and SHALL NOT
be treated as infrastructure failure.

#### Scenario: NO_STABLE_EDGE after adequate investigation

- **WHEN** tested structural regions are flat, unstable, trivially thinned, economically nonviable
  at the required stage, or fail validation with no justified next discriminating experiment
- **THEN** the worker may conclude `NO_STABLE_EDGE`, preserving the negative findings and blockers.

### Requirement: No scalar leaderboard invariant

No policy field, assessment, supervisor action, or promotion decision SHALL reduce candidate quality
to one scalar or weighted score. Optuna, Bayesian optimization, generic ML ranking, highest-return
selection, PF leaderboards, and automatic deletion of negative experiments remain out of scope.

#### Scenario: One metric is numerically best

- **WHEN** a candidate is best on one numeric metric
- **THEN** that fact alone cannot cause automatic selection, promotion, or deletion of alternatives.
