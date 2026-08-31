## Context

BBB AutoResearch v1 already separates the mechanical supervisor from the scientific worker. The
canonical batch result supplies the facts currently available for quality reasoning:

- aggregate `realised_trade_count`, `open_position_count`, `final_equity`, `gross_pnl`,
  `fees_paid`, `net_pnl`, `return_pct`, nullable `win_rate`, nullable `profit_factor`, and
  trade-close `max_drawdown`;
- long and short `trades`, `net_pnl`, `return_pct`, nullable `win_rate`, and nullable
  `profit_factor`;
- canonical run/batch identities, market-data hash, immutable artifacts, and raw trades when a
  justified diagnostic needs them.

The canonical formulas are already fixed: net PnL is gross PnL less fees, return is net PnL divided
by positive initial equity, PF uses after-fee trade PnL, and drawdown is a negative-or-zero
trade-close equity fraction. This change consumes those facts; it does not recompute them or add a
second metrics implementation.

Current AutoResearch phase is intentionally a flexible string. The EMA method nevertheless has
distinct scientific stages: descriptive baseline, structural entry discovery under a fixed neutral
exit, interaction/region discovery, stable entry-region selection, exit geometry, and robustness.
The policy must make those roles explicit without replacing the domain methodology with a brittle
EMA-specific transition machine.

## Goals / Non-Goals

Goals:

- distinguish operational experiment completion, information value, strategy-region quality, and
  promotion readiness;
- formalize four layers: information, structure, economics, and robustness;
- make metric priority stage-aware and durable;
- permit configured mechanical gates without arbitrary default thresholds;
- represent directional effects and multi-objective trade-offs without winner selection;
- retain informative failures and `NO_STABLE_EDGE` conclusions.

Non-goals:

- a weighted score, optimizer, search scheduler, PF/win-rate leaderboard, Bayesian/ML ranking, or
  automatic parameter selection;
- new evaluator metrics, statistical estimators, execution/accounting behavior, or production
  service changes;
- hardcoded profitability, drawdown, win-rate, or trade-count targets;
- changing the EMA skill into a configuration or persistence layer.

## Decision 1: Three independent meanings of success

The design uses three independent axes:

1. **Operational result** — the existing iteration/batch process completed or failed.
2. **Research result** — the experiment was `informative`, `limited`, or `uninformative`.
3. **Promotion result** — a region is discoverable, investigable, economically viable, validated,
   rejected, or supports `NO_STABLE_EDGE`.

An operationally completed, after-cost losing sweep can be an informative research success. An
operationally completed and profitable isolated spike can still fail promotion. These states must
never be collapsed into one boolean or scalar.

## Decision 2: Flexible phases bind to stable stage kinds

`ResearchQualityPolicy.v1` contains explicit `phase_bindings`. The existing session `phase` remains
an operator/domain string; each allowed value maps to exactly one stage kind:

- `descriptive_baseline`
- `structural_entry`
- `structural_interaction`
- `entry_region_selection`
- `exit_geometry`
- `robustness_validation`

The supervisor validates that the current phase has one unambiguous binding. It does not decide the
next phase. The worker and domain methodology still own scientific progression.

## Decision 3: Metric role is stage-specific

Each assessment records four disjoint roles: `descriptive`, `primary`, `secondary`, and
`promotion_gates`. The stage kind fixes their meaning; an operator may configure thresholds but may
not relabel Phase-B PF as its sole primary objective.

| Stage kind | Descriptive/control facts | Primary evidence | Secondary/sanity evidence | Promotion gates |
|---|---|---|---|---|
| `descriptive_baseline` | opportunity/trade count, long/short distribution, hit behavior, gross/fees/net, PF, return, drawdown | adequacy and comparability of the control | none used to optimize | none |
| `structural_entry` | shared-window/control identities and all canonical metrics | win/hit-rate uplift versus naked baseline, long/short hit behavior, response topology, neighborhood behavior, trade count and thinning | PF, gross/net/return, fees, drawdown | evidence completeness only; no profitability rejection |
| `structural_interaction` | comparable surface/slice identities | ridge/plateau/surface topology, perturbation stability, conditional entry-quality behavior, sample and side behavior | PF, gross/net/return, fees, drawdown | structural support only; no final-economics gate |
| `entry_region_selection` | prior structural evidence | stable region, after-cost direction, risk, meaningful sample, side scope, market interpretation and competing explanation | other canonical metrics | positive after-cost economics, neighborhood support, configured thresholds, required directional/validation evidence |
| `exit_geometry` | fixed entry-region identity and symmetric control | net/return after costs, PF, trade-close drawdown, realistic payoff geometry, trade count, side economics, neighboring exit stability | hit rate and diagnostic facts | positive after-cost economics plus configured gates |
| `robustness_validation` | discovery and validation universe identities | holdout/temporal/regime/side/perturbation evidence, sample persistence, topology persistence, justified alternate window/ticker evidence | discovery-window economics | no failed required validation, neighborhood support, positive after-cost economics, configured gates |

Consequences:

- Phase-A economic fields are recorded control facts, not optimization targets.
- Phase-B symmetric-exit net PnL near zero cannot by itself reject structural entry quality.
- Phase-B win rate is primary evidence but cannot outrank trade count, thinning, topology,
  neighborhood stability, or side behavior.
- Economic viability becomes mandatory only when carrying a stable entry region into exit research
  or making a later promotion claim.
- Phase-C economics are not interchangeable with Phase-B neutral/symmetric-exit economics.

## Decision 4: Resolved session policy contract

The implementation SHALL introduce this nested contract without mutating its meaning at runtime:

```text
ResearchQualityPolicy.v1
  contract_version: "bbb_research_quality_policy.v1"
  policy_id: non-empty string
  provenance:
    source: "session" | "strategy_family" | "resolved_combination"
    references: string[]
    rationale: non-empty string
  phase_bindings: PhaseBinding[]
    phase: non-empty string, unique
    stage_kind: one of the six stage kinds
  promotion_thresholds:
    minimum_realised_trade_count: integer >= 1 | null
    minimum_profit_factor: decimal string > 0 | null
    minimum_after_cost_return: decimal string > 0 | null
    maximum_trade_close_drawdown_magnitude: decimal string >= 0 | null
    minimum_long_trade_count: integer >= 1 | null
    minimum_short_trade_count: integer >= 1 | null
    maximum_trade_count_reduction_fraction: decimal string in [0, 1] | null
  side_policy:
    promotable_classifications: unique SideClassification[]
  validation_policy:
    required_before_entry_region_promotion: boolean
    required_evidence: unique ValidationEvidenceKind[]
```

This is a fully resolved, immutable session snapshot. If a strategy-family policy and an operator
policy are composed, composition occurs before session initialization and the resolved values plus
provenance are persisted. The supervisor does not perform hidden precedence or fetch mutable policy
at runtime.

Every threshold field is required but nullable. `null` means no numeric threshold exists and the
supervisor must not invent one. No field can disable the hard positive-after-cost or neighborhood
invariants. `required_evidence` uses: `parameter_perturbation`, `temporal_holdout`, `regime_split`,
`side_decomposition`, `alternate_window`, and `alternate_ticker`. Alternate market evidence is
required only when explicitly configured or methodologically claimed.

## Decision 5: Durable assessment contract

Each quality-aware iteration carries one exact `ResearchQualityAssessment.v1`:

```text
ResearchQualityAssessment.v1
  contract_version: "bbb_research_quality_assessment.v1"
  applied_policy_id: non-empty string
  stage:
    phase: non-empty string
    stage_kind: StageKind
    metric_roles:
      descriptive: MetricOrEvidenceName[]
      primary: MetricOrEvidenceName[]
      secondary: MetricOrEvidenceName[]
      promotion_gates: GateId[]
  promotion_subject: PromotionSubject | null
    region_id: non-empty string
    baseline_candidate_id: string | null
    representative_candidate_ids: unique non-empty string[]
    neighborhood_candidate_ids: unique string[]
  information_value:
    status: "informative" | "limited" | "uninformative"
    outcomes: unique InformationOutcome[]
    rationale: non-empty string
    evidence_refs: EvidenceRef[]
  structural_promise:
    status: "promising" | "not_promising" | "insufficient_evidence" | "not_applicable"
    baseline_comparison: "improved" | "mixed" | "unchanged" | "degraded" | "not_applicable"
    topology: non-empty string | null
    neighborhood_stability: "supported" | "unsupported" | "not_tested" | "not_applicable"
    sample_adequacy: "adequate" | "thin" | "unknown" | "not_applicable"
    economic_direction: "improved" | "mixed" | "unchanged" | "degraded" | "not_applicable"
    market_state_interpretation: non-empty string | null
    competing_explanation: non-empty string | null
    rationale: non-empty string
  economic_viability:
    status: "viable" | "not_viable" | "insufficient_evidence" | "not_applicable"
    after_cost_status: "positive" | "zero" | "negative" | "mixed" | "unknown" | "not_applicable"
    metric_consistency: "consistent" | "inconsistent" | "not_assessed"
    gate_results: GateResult[]
    rationale: non-empty string
  robustness:
    status: "supported" | "failed" | "insufficient_evidence" | "not_tested" | "not_applicable"
    dimensions: RobustnessDimension[]
    rationale: non-empty string
  side_assessment:
    classification: SideClassification
    claim_scope: "two_sided" | "long_only" | "short_only" | "regime_specific" |
                 "unresolved" | "not_applicable"
    rationale: non-empty string
  tradeoff_summary:
    comparisons: TradeoffComparison[]
    rationale: non-empty string
  promotion:
    decision: PromotionDecision
    blockers: PromotionBlocker[]
    rationale: non-empty string
```

`InformationOutcome` includes `flat_response`, `monotonic_response`, `threshold`, `plateau`,
`broad_optimum`, `isolated_spike`, `boundary_running`, `u_shape`, `inverted_u`,
`side_asymmetry`, `thinning_detected`, `temporal_concentration_detected`,
`regime_concentration_detected`, `hypothesis_supported`, and `hypothesis_rejected`.

`SideClassification` is one of `two_sided_consistent`, `long_dominant`, `short_dominant`,
`regime_specific_directional`, `aggregate_masks_side_failure`, `mixed_unresolved`, or
`not_applicable`. `two_sided_consistent` is evidence toward universality, not permission to claim a
universal edge before robustness. A directional classification requires temporal/regime validation
before strong promotion and cannot be described as two-sided.

`PromotionDecision` is one of `continue_discovery`, `investigate_region`,
`eligible_for_next_stage`, `validation_required`, `rejected_structurally`,
`demoted_after_validation`, or `no_stable_edge`. It is a disposition of a research region, never a
winner-selection result.

The supporting types are exact rather than free-form semantic bags:

```text
EvidenceRef
  kind: "canonical_metric" | "prior_assessment" | "analysis_artifact"
  claim_id: non-empty string
  candidate_id: string | null
  metric_path: CanonicalMetricPath | null
  iteration_id: integer >= 1 | null
  analysis_path: non-empty string | null

GateResult
  gate_id: GateId
  source: "hard_invariant" | "configured_threshold"
  candidate_ids: unique non-empty string[]
  threshold: decimal/integer string | null
  observed_by_candidate: object keyed by candidate ID
  status: "pass" | "fail"
  evidence_refs: non-empty EvidenceRef[]

RobustnessDimension
  dimension: "neighborhood" | "parameter_perturbation" | "sample_size" | "thinning" |
             "temporal" | "regime" | "side" | "holdout" | "alternate_window" |
             "alternate_ticker"
  status: "supported" | "failed" | "not_tested" | "not_available" | "not_applicable"
  evidence_refs: EvidenceRef[]
  rationale: non-empty string

TradeoffComparison
  left_subject_ref: non-empty string
  right_subject_ref: non-empty string
  stage_kind: StageKind
  same_market_universe: boolean
  dimensions: non-empty TradeoffDimension[]
    dimension: "profitability" | "absolute_after_cost_result" | "risk" | "sample_size" |
               "side_breadth" | "neighborhood_stability"
    assessment: "left_better" | "right_better" | "equivalent" | "uncertain"
    evidence_refs: EvidenceRef[]
  relation: "left_dominates" | "right_dominates" | "tradeoff" | "equivalent" |
            "incomparable"

PromotionBlocker
  code: "missing_evidence" | "no_structural_response" | "isolated_spike" |
        "boundary_unresolved" | "thin_sample" | "configured_gate_failed" |
        "after_cost_nonpositive" | "economic_inconsistency" |
        "neighborhood_unsupported" | "directional_validation_missing" |
        "required_validation_missing" | "validation_failed" |
        "temporal_concentration" | "regime_concentration" | "side_masking" | "other"
  gate_id: GateId | null
  message: non-empty string
  evidence_refs: EvidenceRef[]
```

`CanonicalMetricPath` is restricted to the fields already present in canonical batch summaries:
aggregate accounting totals/derived metrics and the existing long/short summary fields. A reference
does not authorize a new calculation. Kind-specific nullability is enforced: canonical metric refs
require candidate/metric, prior refs require iteration, and analysis refs require an analysis path.

`GateId` is one of `after_cost_positive`, `economic_metric_consistency`,
`neighborhood_supported`, `minimum_realised_trade_count`, `minimum_profit_factor`,
`minimum_after_cost_return`, `maximum_trade_close_drawdown_magnitude`,
`minimum_long_trade_count`, `minimum_short_trade_count`,
`maximum_trade_count_reduction_fraction`, `side_classification_permitted`, or
`required_validation`. Metric/evidence names in `stage.metric_roles` use only canonical metric paths
plus `baseline_uplift`, `response_topology`, `neighborhood_stability`, `payoff_geometry`,
`thinning`, `temporal_concentration`, `regime_concentration`, and `validation_evidence`. The metric
role table above is normative; the supervisor validates membership rather than accepting arbitrary
worker relabeling.

Full assessments belong in retained iteration results and journal rows. Compact state persists the
immutable `research_quality_policy`, active stage binding, `latest_quality_assessment`, and a compact
promotion history containing region ID, decision, and blockers. The supervisor copies worker-owned
semantic fields mechanically; it does not infer topology, side class, or scientific meaning.

Because current enclosing schemas are exact and versioned, implementation introduces
`bbb_autoresearch_iteration.v2`, `bbb_autoresearch_state.v2`, and a journal version capable of
carrying the assessment. V1 documents remain v1 documents; no silent in-place shape expansion is
allowed.

## Decision 6: Hard economic consistency and configurable gates

For a promotion subject in `entry_region_selection`, `exit_geometry`, or
`robustness_validation`, every representative candidate must satisfy the non-configurable
after-cost invariant:

- `net_pnl > 0` and `return_pct > 0`;
- `gross_pnl - fees_paid == net_pnl` as guaranteed by the canonical evaluator;
- the sign of `return_pct` agrees with the sign of `net_pnl`;
- a non-null PF agrees directionally with after-cost economics (`> 1` positive, `= 1` flat,
  `< 1` negative). Null PF is consistent with viability only for a nonzero-trade, positive-net
  canonical result, matching the existing no-losing-trades null semantics.

The supervisor checks existing canonical facts and references; it does not recalculate trades or
metrics. A configured numeric threshold produces a mandatory `GateResult` and is checked for every
representative candidate. A null threshold produces no implicit gate. A configured PF threshold
with null PF uses the canonical null semantics above rather than treating null as zero.

An economically negative Phase-B region may remain structurally promising. It simply cannot be
declared a final viable entry region or promoted beyond the point where positive after-cost
economics is required.

## Decision 7: Neighborhood and validation are not numeric leaderboards

A profitable isolated spike or unsupported boundary point cannot receive
`eligible_for_next_stage`. Neighborhood support is a hard promotion invariant, but v1 does not
invent a universal neighbor count or distance. The worker identifies the relevant neighborhood from
the experiment axes and supplies candidate references and rationale; the supervisor validates that
the referenced candidates exist and that the assessment reports support.

Robustness dimensions are explicit: `neighborhood`, `parameter_perturbation`, `sample_size`,
`thinning`, `temporal`, `regime`, `side`, `holdout`, `alternate_window`, and `alternate_ticker`.
Each is `supported`, `failed`, `not_tested`, `not_available`, or `not_applicable`, with evidence.
Any failed required dimension blocks promotion and may produce `demoted_after_validation`.

## Decision 8: Pareto-like comparison is descriptive, not optimizing

`TradeoffComparison` compares two named candidates or regions across these objective dimensions:
profitability, absolute after-cost result, risk, sample size, side breadth, and neighborhood
stability. Each dimension records `left_better`, `right_better`, `equivalent`, or `uncertain` with
evidence. Overall relation is `left_dominates`, `right_dominates`, `tradeoff`, `equivalent`, or
`incomparable`.

Domination is valid only for subjects evaluated in the same stage and comparable market universe,
when one is no worse on every applicable dimension, strictly better on at least one, and no required
dimension is uncertain. Mixed advantages are a `tradeoff`; missing comparability is `incomparable`.
Neither relation authorizes the supervisor to select a candidate. The worker uses it to explain the
next information-gaining experiment or region-level disposition.

Thus higher PF with collapsed trade count does not dominate, and a lower-PF broad stable region can
remain investigable or promotable if the complete stage-appropriate evidence supports it.

## Responsibility boundary

Supervisor responsibilities:

- validate exact policy/assessment contracts and immutable policy identity;
- validate phase binding and stage-specific required assessment sections;
- verify evidence references identify retained canonical candidates/artifacts;
- mechanically enforce hard invariants and configured gates when promotion is claimed;
- persist the worker's explicit assessment and blockers;
- never rank, score, infer scientific semantics, or choose a numeric winner.

Worker responsibilities:

- interpret topology, baseline uplift, neighborhood, thinning, concentration, sides, and competing
  explanations;
- produce multi-metric comparison and explicit side classification;
- distinguish information value from strategy viability;
- choose the next highest-information experiment and make only policy-permitted promotion claims.

Evaluator responsibilities:

- continue producing canonical execution/accounting facts and immutable artifacts;
- remain unchanged and unaware of research-quality policy.

The EMA skill remains domain methodology and causal-order authority. It is referenced by the worker,
not used as a storage/configuration implementation.

## Hard invariants versus configurable policy

Hard invariants, not operator-relaxable:

- operational completion, information value, and promotion are distinct;
- negative but informative experiments and failed validation remain durable;
- no scalar/weighted winner selection;
- phase-specific metric roles follow the normative stage table;
- Phase A is descriptive and Phase B economics cannot act as a final-economics pruning gate;
- final entry/later promotion requires positive, internally consistent after-cost economics;
- isolated spikes or unsupported neighborhoods cannot be promoted;
- directional findings have narrow scope and require directional temporal/regime validation before
  strong promotion;
- required validation failure blocks or demotes promotion;
- `aggregate_masks_side_failure` and `mixed_unresolved` are not promotable side classifications;
- supervisor interpretation remains mechanical and the evaluator remains unchanged.

Configurable in the immutable resolved policy:

- mapping of domain phase strings to the six stage kinds;
- optional numeric thresholds, each nullable with no implicit default;
- which of the otherwise promotable side classifications the session permits;
- whether entry-region promotion requires validation before exit research and which validation
  evidence kinds are required;
- policy provenance and rationale.

`promotable_classifications` may contain only `two_sided_consistent`, `long_dominant`,
`short_dominant`, and `regime_specific_directional`. Directional validation remains mandatory even
when a directional class is permitted. If validation is configured as required,
`required_evidence` must be non-empty.

## Risks / Trade-offs

- Structured assessments add verbosity. Compact state therefore keeps only the latest assessment
  and promotion history; retained iterations/journal preserve full evidence.
- Qualitative neighborhood and regime judgments cannot be proven mechanically without inventing a
  statistical model. The contract makes evidence and responsibility explicit instead.
- Optional thresholds improve reproducibility but can encode poor operator policy. Hard invariants
  prevent thresholds from legalizing scalar winner selection, isolated spikes, or negative
  after-cost final regions.

## Unresolved questions

1. Whether a later strategy-family policy registry should exist, or resolved policy files should
   remain session-template inputs only.
2. Whether neighborhood evidence needs a future typed geometry contract beyond candidate IDs,
   axis coordinates, and rationale.
3. Which temporal/regime diagnostics are reliably available without adding evaluator metrics; v1
   permits `not_available` and must not fabricate them.
4. Whether an explicit migration CLI for active v1 sessions is worth supporting; silent migration
   is ruled out.
5. Whether future statistical confidence/uncertainty contracts are justified. They are not inferred
   from trade count in this version.
