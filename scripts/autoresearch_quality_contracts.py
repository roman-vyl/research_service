#!/usr/bin/env python3
"""Exact contracts and mechanical policy checks for AutoResearch quality v1."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, model_validator

from research_service.application.experiments.contracts import BatchExperimentRequest

QUALITY_POLICY_VERSION = "bbb_research_quality_policy.v1"
QUALITY_ASSESSMENT_VERSION = "bbb_research_quality_assessment.v1"

StageKind = Literal[
    "descriptive_baseline",
    "structural_entry",
    "structural_interaction",
    "entry_region_selection",
    "exit_geometry",
    "robustness_validation",
]
SideClassification = Literal[
    "two_sided_consistent",
    "long_dominant",
    "short_dominant",
    "regime_specific_directional",
    "aggregate_masks_side_failure",
    "mixed_unresolved",
    "not_applicable",
]
ValidationEvidenceKind = Literal[
    "parameter_perturbation",
    "temporal_holdout",
    "regime_split",
    "side_decomposition",
    "alternate_window",
    "alternate_ticker",
]
GateId = Literal[
    "after_cost_positive",
    "economic_metric_consistency",
    "neighborhood_supported",
    "minimum_realised_trade_count",
    "minimum_profit_factor",
    "minimum_after_cost_return",
    "maximum_trade_close_drawdown_magnitude",
    "minimum_long_trade_count",
    "minimum_short_trade_count",
    "maximum_trade_count_reduction_fraction",
    "side_classification_permitted",
    "required_validation",
]

CANONICAL_METRIC_PATHS = frozenset(
    {
        "realised_trade_count",
        "open_position_count",
        "final_equity",
        "gross_pnl",
        "fees_paid",
        "net_pnl",
        "return_pct",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "long.trades",
        "long.net_pnl",
        "long.return_pct",
        "long.win_rate",
        "long.profit_factor",
        "short.trades",
        "short.net_pnl",
        "short.return_pct",
        "short.win_rate",
        "short.profit_factor",
    }
)
SEMANTIC_EVIDENCE_NAMES = frozenset(
    {
        "baseline_uplift",
        "response_topology",
        "neighborhood_stability",
        "payoff_geometry",
        "thinning",
        "temporal_concentration",
        "regime_concentration",
        "validation_evidence",
    }
)
METRIC_OR_EVIDENCE_NAMES = CANONICAL_METRIC_PATHS | SEMANTIC_EVIDENCE_NAMES


def _decimal_string(value: Any) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("decimal values must be non-empty strings")
    try:
        return Decimal(value)
    except Exception as exc:
        raise ValueError("invalid decimal string") from exc


DecimalString = Annotated[
    Decimal,
    BeforeValidator(_decimal_string),
    WithJsonSchema({"type": "string", "pattern": r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"}),
]
NumericString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]

DESCRIPTIVE_ECONOMICS = {
    "gross_pnl",
    "fees_paid",
    "net_pnl",
    "return_pct",
    "profit_factor",
    "max_drawdown",
}
BASELINE_PRIMARY_ALLOWED = {
    "realised_trade_count",
    "open_position_count",
    "long.trades",
    "short.trades",
}
CONDITIONAL_ENTRY_EVIDENCE = {
    "baseline_uplift",
    "win_rate",
    "long.win_rate",
    "short.win_rate",
}
SAMPLE_THINNING_EVIDENCE = {"realised_trade_count", "thinning"}
SIDE_BEHAVIOR_EVIDENCE = {"long.win_rate", "short.win_rate"}
STRUCTURAL_PRIMARY_ALLOWED = {
    "baseline_uplift",
    "response_topology",
    "neighborhood_stability",
    "realised_trade_count",
    "win_rate",
    "long.win_rate",
    "short.win_rate",
    "thinning",
    "temporal_concentration",
    "regime_concentration",
}
EXIT_PRIMARY = {
    "net_pnl",
    "return_pct",
    "profit_factor",
    "max_drawdown",
    "payoff_geometry",
    "realised_trade_count",
    "long.net_pnl",
    "long.return_pct",
    "long.profit_factor",
    "short.net_pnl",
    "short.return_pct",
    "short.profit_factor",
    "neighborhood_stability",
}
ROBUSTNESS_PRIMARY = {
    "validation_evidence",
    "neighborhood_stability",
    "realised_trade_count",
    "thinning",
    "temporal_concentration",
    "regime_concentration",
}
ROBUSTNESS_PRIMARY_ALLOWED = ROBUSTNESS_PRIMARY | {
    "response_topology",
    "win_rate",
    "long.trades",
    "long.win_rate",
    "short.trades",
    "short.win_rate",
}


class ExactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(ExactModel):
    source: Literal["session", "strategy_family", "resolved_combination"]
    references: list[str]
    rationale: str = Field(min_length=1)


class PhaseBinding(ExactModel):
    phase: str = Field(min_length=1)
    stage_kind: StageKind


class PromotionThresholds(ExactModel):
    minimum_realised_trade_count: int | None = Field(ge=1)
    minimum_profit_factor: DecimalString | None = Field(gt=0)
    minimum_after_cost_return: DecimalString | None = Field(gt=0)
    maximum_trade_close_drawdown_magnitude: DecimalString | None = Field(ge=0)
    minimum_long_trade_count: int | None = Field(ge=1)
    minimum_short_trade_count: int | None = Field(ge=1)
    maximum_trade_count_reduction_fraction: DecimalString | None = Field(ge=0, le=1)


class SidePolicy(ExactModel):
    promotable_classifications: list[
        Literal[
            "two_sided_consistent",
            "long_dominant",
            "short_dominant",
            "regime_specific_directional",
        ]
    ]

    @model_validator(mode="after")
    def unique(self) -> "SidePolicy":
        if len(self.promotable_classifications) != len(set(self.promotable_classifications)):
            raise ValueError("promotable_classifications must be unique")
        return self


class ValidationPolicy(ExactModel):
    required_before_entry_region_promotion: bool
    required_evidence: list[ValidationEvidenceKind]

    @model_validator(mode="after")
    def coherent(self) -> "ValidationPolicy":
        if len(self.required_evidence) != len(set(self.required_evidence)):
            raise ValueError("required_evidence must be unique")
        if self.required_before_entry_region_promotion and not self.required_evidence:
            raise ValueError("required_evidence cannot be empty when validation is required")
        return self


class ResearchQualityPolicy(ExactModel):
    contract_version: Literal["bbb_research_quality_policy.v1"]
    policy_id: str = Field(min_length=1)
    provenance: Provenance
    phase_bindings: list[PhaseBinding] = Field(min_length=1)
    promotion_thresholds: PromotionThresholds
    side_policy: SidePolicy
    validation_policy: ValidationPolicy

    @model_validator(mode="after")
    def unique_phases(self) -> "ResearchQualityPolicy":
        phases = [binding.phase for binding in self.phase_bindings]
        if len(phases) != len(set(phases)):
            raise ValueError("phase_bindings phases must be unique")
        return self


class MetricRoles(ExactModel):
    descriptive: list[str]
    primary: list[str]
    secondary: list[str]
    promotion_gates: list[GateId]

    @model_validator(mode="after")
    def exact_role_names(self) -> "MetricRoles":
        role_lists = (self.descriptive, self.primary, self.secondary)
        if any(len(values) != len(set(values)) for values in role_lists):
            raise ValueError("metric role values must be unique")
        unknown = set().union(*map(set, role_lists)) - METRIC_OR_EVIDENCE_NAMES
        if unknown:
            raise ValueError(f"unknown metric/evidence role names: {sorted(unknown)}")
        if set(self.descriptive) & set(self.primary) or set(self.descriptive) & set(self.secondary):
            raise ValueError("metric roles must be disjoint")
        if set(self.primary) & set(self.secondary):
            raise ValueError("metric roles must be disjoint")
        if len(self.promotion_gates) != len(set(self.promotion_gates)):
            raise ValueError("promotion_gates must be unique")
        return self


class MetricRoleSelection(ExactModel):
    """The narrow worker-facing input `materialize_metric_roles` compiles into a full
    `MetricRoles` object. Only the fields the stage-kind audit found to carry genuine
    evidentiary judgment: which additional named evidence to cite in `primary` beyond the
    stage's mandatory core (the worker's only real choice for `structural_entry`/
    `structural_interaction`/`entry_region_selection`/`robustness_validation`; always empty for
    `descriptive_baseline`/`exit_geometry`, which have no optional primary evidence), and which
    promotion gates apply this iteration (always empty for `descriptive_baseline`, which defines
    none). The worker never authors `secondary`/`descriptive`, and never authors the mandatory
    part of `primary` -- see `materialize_metric_roles`."""

    primary_evidence_additions: list[str] = Field(default_factory=list)
    promotion_gates: list[GateId] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique(self) -> "MetricRoleSelection":
        if len(self.primary_evidence_additions) != len(set(self.primary_evidence_additions)):
            raise ValueError("primary_evidence_additions must be unique")
        if len(self.promotion_gates) != len(set(self.promotion_gates)):
            raise ValueError("promotion_gates must be unique")
        return self


# Stage-fixed MetricRoles content the audit found to be fully or mostly deterministic --
# materialize_metric_roles builds the complete object from this plus the worker's narrow
# MetricRoleSelection, never asking the worker to reproduce it. Each entry mirrors exactly what
# validate_metric_roles already enforces for that stage_kind (see that function for the
# authoritative mechanical constraints this table must stay consistent with).
_METRIC_ROLES_FIXED_CORE: dict[StageKind, dict[str, Any]] = {
    "descriptive_baseline": {
        "primary_core": BASELINE_PRIMARY_ALLOWED,
        "secondary": frozenset(),
        "descriptive": None,  # computed as CANONICAL_METRIC_PATHS - primary, see materializer
    },
    "structural_entry": {
        "primary_core": {"response_topology"},
        "secondary": frozenset({"net_pnl", "return_pct", "profit_factor", "max_drawdown"}),
        "descriptive": frozenset({"gross_pnl", "fees_paid"}),
    },
    "structural_interaction": {
        "primary_core": {"response_topology", "neighborhood_stability"},
        "secondary": frozenset({"net_pnl", "return_pct", "profit_factor", "max_drawdown"}),
        "descriptive": frozenset({"gross_pnl", "fees_paid"}),
    },
    "entry_region_selection": {
        "primary_core": {"response_topology", "neighborhood_stability"},
        "secondary": frozenset({"net_pnl", "return_pct", "profit_factor", "max_drawdown"}),
        "descriptive": frozenset({"gross_pnl", "fees_paid"}),
    },
    "exit_geometry": {
        "primary_core": EXIT_PRIMARY,
        "secondary": frozenset({"win_rate"}),
        "descriptive": frozenset({"gross_pnl", "fees_paid"}),
    },
    "robustness_validation": {
        "primary_core": ROBUSTNESS_PRIMARY,
        "secondary": frozenset({"net_pnl"}),
        "descriptive": frozenset({"gross_pnl", "fees_paid"}),
    },
}


def materialize_metric_roles(stage_kind: StageKind, selection: MetricRoleSelection) -> MetricRoles:
    """Deterministically compile the complete `MetricRoles` object for `stage_kind` from the
    worker's narrow `MetricRoleSelection`, per the fixed core in `_METRIC_ROLES_FIXED_CORE`. The
    result still passes through the unchanged `validate_metric_roles` before acceptance -- this
    function performs no independent business-rule enforcement of its own; a selection that
    produces an invalid union (e.g. missing a required "at least one of" evidence set) is caught
    there, not here."""
    fixed = _METRIC_ROLES_FIXED_CORE[stage_kind]
    primary = sorted(set(fixed["primary_core"]) | set(selection.primary_evidence_additions))
    descriptive = fixed["descriptive"]
    if descriptive is None:
        descriptive = CANONICAL_METRIC_PATHS - set(primary)
    return MetricRoles(
        primary=primary,
        secondary=sorted(fixed["secondary"]),
        descriptive=sorted(descriptive),
        promotion_gates=sorted(selection.promotion_gates),
    )


class StageAssessment(ExactModel):
    phase: str = Field(min_length=1)
    stage_kind: StageKind
    metric_roles: MetricRoles


class PromotionSubject(ExactModel):
    region_id: str = Field(min_length=1)
    baseline_candidate_id: str | None
    representative_candidate_ids: list[str]
    neighborhood_candidate_ids: list[str]

    @model_validator(mode="after")
    def unique_ids(self) -> "PromotionSubject":
        for name in ("representative_candidate_ids", "neighborhood_candidate_ids"):
            values = getattr(self, name)
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError(f"{name} must contain unique non-empty strings")
        return self


class EvidenceRef(ExactModel):
    kind: Literal["canonical_metric", "prior_assessment", "analysis_artifact"]
    claim_id: str = Field(min_length=1)
    candidate_id: str | None
    metric_path: str | None
    iteration_id: int | None = Field(ge=1)
    analysis_path: str | None

    @model_validator(mode="after")
    def kind_shape(self) -> "EvidenceRef":
        if self.kind == "canonical_metric":
            if not self.candidate_id or self.metric_path not in CANONICAL_METRIC_PATHS:
                raise ValueError("canonical_metric evidence requires candidate_id and metric_path")
            if self.iteration_id is not None or self.analysis_path is not None:
                raise ValueError("canonical_metric evidence has invalid fields")
        elif self.kind == "prior_assessment":
            if self.iteration_id is None:
                raise ValueError("prior_assessment evidence requires iteration_id")
            if (
                self.candidate_id is not None
                or self.metric_path is not None
                or self.analysis_path is not None
            ):
                raise ValueError("prior_assessment evidence has invalid fields")
        else:
            if not self.analysis_path:
                raise ValueError("analysis_artifact evidence requires analysis_path")
            if (
                self.candidate_id is not None
                or self.metric_path is not None
                or self.iteration_id is not None
            ):
                raise ValueError("analysis_artifact evidence has invalid fields")
        return self


class InformationValue(ExactModel):
    status: Literal["informative", "limited", "uninformative"]
    outcomes: list[
        Literal[
            "flat_response",
            "monotonic_response",
            "threshold",
            "plateau",
            "broad_optimum",
            "isolated_spike",
            "boundary_running",
            "u_shape",
            "inverted_u",
            "side_asymmetry",
            "thinning_detected",
            "temporal_concentration_detected",
            "regime_concentration_detected",
            "hypothesis_supported",
            "hypothesis_rejected",
        ]
    ]
    rationale: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef]

    @model_validator(mode="after")
    def unique_outcomes(self) -> "InformationValue":
        if len(self.outcomes) != len(set(self.outcomes)):
            raise ValueError("information outcomes must be unique")
        return self


class StructuralPromise(ExactModel):
    status: Literal["promising", "not_promising", "insufficient_evidence", "not_applicable"]
    baseline_comparison: Literal["improved", "mixed", "unchanged", "degraded", "not_applicable"]
    topology: str | None
    neighborhood_stability: Literal["supported", "unsupported", "not_tested", "not_applicable"]
    sample_adequacy: Literal["adequate", "thin", "unknown", "not_applicable"]
    economic_direction: Literal["improved", "mixed", "unchanged", "degraded", "not_applicable"]
    market_state_interpretation: str | None
    competing_explanation: str | None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def nullable_strings(self) -> "StructuralPromise":
        for name in ("topology", "market_state_interpretation", "competing_explanation"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValueError(f"{name} must be non-empty or null")
        return self


class GateResult(ExactModel):
    gate_id: GateId
    source: Literal["hard_invariant", "configured_threshold"]
    candidate_ids: list[str]
    threshold: NumericString | None
    observed_by_candidate: dict[str, str | int | bool | None]
    status: Literal["pass", "fail"]
    evidence_refs: list[EvidenceRef] = Field(min_length=1)

    @model_validator(mode="after")
    def candidate_shape(self) -> "GateResult":
        if any(not item for item in self.candidate_ids) or len(self.candidate_ids) != len(
            set(self.candidate_ids)
        ):
            raise ValueError("gate candidate_ids must be unique non-empty strings")
        if set(self.observed_by_candidate) != set(self.candidate_ids):
            raise ValueError("observed_by_candidate keys must equal candidate_ids")
        if self.source == "configured_threshold" and self.threshold is None:
            raise ValueError("configured threshold gate requires threshold")
        if self.source == "hard_invariant" and self.threshold is not None:
            raise ValueError("hard invariant gate threshold must be null")
        return self


class EconomicViability(ExactModel):
    status: Literal["viable", "not_viable", "insufficient_evidence", "not_applicable"]
    after_cost_status: Literal["positive", "zero", "negative", "mixed", "unknown", "not_applicable"]
    metric_consistency: Literal["consistent", "inconsistent", "not_assessed"]
    gate_results: list[GateResult]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_gates(self) -> "EconomicViability":
        ids = [gate.gate_id for gate in self.gate_results]
        if len(ids) != len(set(ids)):
            raise ValueError("economic gate_results must have unique gate_id values")
        return self


class RobustnessDimension(ExactModel):
    dimension: Literal[
        "neighborhood",
        "parameter_perturbation",
        "sample_size",
        "thinning",
        "temporal",
        "regime",
        "side",
        "holdout",
        "alternate_window",
        "alternate_ticker",
    ]
    status: Literal["supported", "failed", "not_tested", "not_available", "not_applicable"]
    evidence_refs: list[EvidenceRef]
    rationale: str = Field(min_length=1)


class Robustness(ExactModel):
    status: Literal["supported", "failed", "insufficient_evidence", "not_tested", "not_applicable"]
    dimensions: list[RobustnessDimension]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_dimensions(self) -> "Robustness":
        values = [item.dimension for item in self.dimensions]
        if len(values) != len(set(values)):
            raise ValueError("robustness dimensions must be unique")
        return self


class SideAssessment(ExactModel):
    classification: SideClassification
    claim_scope: Literal[
        "two_sided",
        "long_only",
        "short_only",
        "regime_specific",
        "unresolved",
        "not_applicable",
    ]
    rationale: str = Field(min_length=1)


class TradeoffDimension(ExactModel):
    dimension: Literal[
        "profitability",
        "absolute_after_cost_result",
        "risk",
        "sample_size",
        "side_breadth",
        "neighborhood_stability",
    ]
    assessment: Literal["left_better", "right_better", "equivalent", "uncertain"]
    evidence_refs: list[EvidenceRef]


class TradeoffComparison(ExactModel):
    """Compares two subjects the interpretation worker itself chose to compare.

    Technical market-universe identity (same frozen session research horizon,
    matching `market_data_hash`) is a harness-owned invariant, not a worker
    judgment call: the supervisor freezes one research horizon for the whole
    session and fail-closed hard-stops before interpretation if any candidate's
    evidence does not match it (see `research_horizon` in session state). A
    comparison the worker is asked to interpret has therefore already passed
    deterministic comparability checks; this model carries only the scientific
    tradeoff judgment (profitability/risk/sample-size/etc), never a
    provenance/universe declaration.
    """

    left_subject_ref: str = Field(min_length=1)
    right_subject_ref: str = Field(min_length=1)
    stage_kind: StageKind
    dimensions: list[TradeoffDimension] = Field(min_length=1)
    relation: Literal["left_dominates", "right_dominates", "tradeoff", "equivalent", "incomparable"]

    @model_validator(mode="after")
    def relation_is_pareto_consistent(self) -> "TradeoffComparison":
        dimensions = [item.dimension for item in self.dimensions]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("tradeoff dimensions must be unique")
        values = [item.assessment for item in self.dimensions]
        if self.relation == "left_dominates" and (
            "right_better" in values or "uncertain" in values or "left_better" not in values
        ):
            raise ValueError("left_dominates contradicts dimension assessments")
        if self.relation == "right_dominates" and (
            "left_better" in values or "uncertain" in values or "right_better" not in values
        ):
            raise ValueError("right_dominates contradicts dimension assessments")
        if self.relation == "tradeoff" and not ({"left_better", "right_better"} <= set(values)):
            raise ValueError("tradeoff requires mixed advantages")
        if self.relation == "equivalent" and any(value != "equivalent" for value in values):
            raise ValueError("equivalent relation requires equivalent dimensions")
        return self


class TradeoffComparisonSelection(ExactModel):
    """The narrow worker-facing input `derive_tradeoff_relation`/the supervisor compile into a
    full `TradeoffComparison` -- everything except `relation`, which is fully determined by
    `dimensions[].assessment` and therefore materialized deterministically, never worker-authored.
    `ExactModel`'s `extra="forbid"` rejects a submission that still includes `relation`, with no
    separate manual check needed."""

    left_subject_ref: str = Field(min_length=1)
    right_subject_ref: str = Field(min_length=1)
    stage_kind: StageKind
    dimensions: list[TradeoffDimension] = Field(min_length=1)


def derive_tradeoff_relation(
    dimensions: list[TradeoffDimension],
) -> Literal["left_dominates", "right_dominates", "tradeoff", "equivalent", "incomparable"]:
    """Deterministically compute the one `relation` value consistent with `dimensions[].assessment`
    under `relation_is_pareto_consistent`'s exact rules -- a total function whose output always
    passes that unchanged validator. `dimensions` carries the worker's own scientific judgment
    (which assessment each named dimension deserves); this function performs no judgment of its
    own, only the mechanical Pareto consequence of those judgments."""
    values = {item.assessment for item in dimensions}
    if values == {"equivalent"}:
        return "equivalent"
    has_left = "left_better" in values
    has_right = "right_better" in values
    has_uncertain = "uncertain" in values
    if has_left and has_right:
        return "tradeoff"
    if has_left and not has_uncertain:
        return "left_dominates"
    if has_right and not has_uncertain:
        return "right_dominates"
    return "incomparable"


class TradeoffSummary(ExactModel):
    comparisons: list[TradeoffComparison]
    rationale: str = Field(min_length=1)


class PromotionBlocker(ExactModel):
    code: Literal[
        "missing_evidence",
        "no_structural_response",
        "isolated_spike",
        "boundary_unresolved",
        "thin_sample",
        "configured_gate_failed",
        "after_cost_nonpositive",
        "economic_inconsistency",
        "neighborhood_unsupported",
        "directional_validation_missing",
        "required_validation_missing",
        "validation_failed",
        "temporal_concentration",
        "regime_concentration",
        "side_masking",
        "other",
    ]
    gate_id: GateId | None
    message: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef]


class Promotion(ExactModel):
    decision: Literal[
        "continue_discovery",
        "investigate_region",
        "eligible_for_next_stage",
        "validation_required",
        "rejected_structurally",
        "demoted_after_validation",
        "no_stable_edge",
    ]
    blockers: list[PromotionBlocker]
    rationale: str = Field(min_length=1)


class ResearchQualityAssessment(ExactModel):
    contract_version: Literal["bbb_research_quality_assessment.v1"]
    applied_policy_id: str = Field(min_length=1)
    stage: StageAssessment
    promotion_subject: PromotionSubject | None
    information_value: InformationValue
    structural_promise: StructuralPromise
    economic_viability: EconomicViability
    robustness: Robustness
    side_assessment: SideAssessment
    tradeoff_summary: TradeoffSummary
    promotion: Promotion


def validate_policy(value: dict[str, Any]) -> ResearchQualityPolicy:
    return ResearchQualityPolicy.model_validate(value)


def validate_assessment(value: dict[str, Any]) -> ResearchQualityAssessment:
    return ResearchQualityAssessment.model_validate(value)


def phase_binding(policy: ResearchQualityPolicy, phase: str) -> PhaseBinding:
    matches = [binding for binding in policy.phase_bindings if binding.phase == phase]
    if len(matches) != 1:
        raise ValueError(f"phase {phase!r} does not have exactly one policy binding")
    return matches[0]


def describe_metric_role_selection_contract(stage_kind: StageKind) -> str:
    """Render the narrow `MetricRoleSelection` the worker must submit for `stage_kind` --
    everything else in `MetricRoles` (the mandatory `primary` core, `secondary`, `descriptive`) is
    deterministically materialized by the supervisor (`materialize_metric_roles`) from the same
    constants this function reads; the worker never authors it and must not restate it. This
    replaces the former full-`MetricRoles` cheat-sheet (`describe_stage_metric_role_contract`) now
    that the audit backing this change found most of that structure had no worker-facing decision
    content."""
    if stage_kind == "descriptive_baseline":
        return (
            f"Stage: {stage_kind}\n"
            "metric_role_selection: submit `primary_evidence_additions: []` and "
            "`promotion_gates: []` -- this stage has no optional primary evidence and defines no "
            "promotion gates. The complete metric_roles object is materialized by the supervisor; "
            "you author no part of it."
        )
    if stage_kind in {"structural_entry", "structural_interaction", "entry_region_selection"}:
        lines = [
            f"Stage: {stage_kind}",
            "metric_role_selection.primary_evidence_additions must include, from the evidence you "
            "judge reliable enough to cite this iteration:",
            f"  at least one of: {', '.join(sorted(CONDITIONAL_ENTRY_EVIDENCE))}",
            f"  at least one of: {', '.join(sorted(SAMPLE_THINNING_EVIDENCE))}",
        ]
        if stage_kind in {"structural_interaction", "entry_region_selection"}:
            lines.append(f"  at least one of: {', '.join(sorted(SIDE_BEHAVIOR_EVIDENCE))}")
        lines.append(
            "The mandatory primary core (response_topology"
            + (", neighborhood_stability" if stage_kind != "structural_entry" else "")
            + ") and every secondary/descriptive value are materialized by the supervisor -- do "
            "not restate them."
        )
        lines.append(
            "metric_role_selection.promotion_gates: name any gates relevant to this iteration's "
            "promotion claim, except after_cost_positive (forbidden at this stage)."
        )
        return "\n".join(lines)
    if stage_kind == "exit_geometry":
        return (
            f"Stage: {stage_kind}\n"
            "metric_role_selection.primary_evidence_additions must be empty -- this stage's "
            "primary is fixed exactly and materialized by the supervisor.\n"
            "metric_role_selection.promotion_gates must include after_cost_positive."
        )
    return (
        f"Stage: {stage_kind}\n"
        "metric_role_selection.primary_evidence_additions may optionally include any of: "
        f"{', '.join(sorted(ROBUSTNESS_PRIMARY_ALLOWED - ROBUSTNESS_PRIMARY))} -- the mandatory "
        "core is materialized by the supervisor.\n"
        "metric_role_selection.promotion_gates must include after_cost_positive."
    )


def validate_metric_roles(assessment: ResearchQualityAssessment) -> None:
    stage = assessment.stage.stage_kind
    roles = assessment.stage.metric_roles
    primary = set(roles.primary)
    secondary = set(roles.secondary)
    if stage == "descriptive_baseline":
        if not primary or not primary <= BASELINE_PRIMARY_ALLOWED:
            raise ValueError("baseline primary evidence must measure control sample adequacy")
        if "realised_trade_count" not in primary:
            raise ValueError("baseline primary evidence requires realised_trade_count")
        if roles.promotion_gates:
            raise ValueError("baseline cannot define promotion gates")
    elif stage in {"structural_entry", "structural_interaction", "entry_region_selection"}:
        if not primary <= STRUCTURAL_PRIMARY_ALLOWED:
            raise ValueError("structural stage contains an invalid primary metric role")
        if not secondary or not secondary <= DESCRIPTIVE_ECONOMICS:
            raise ValueError("structural stages must keep economics in secondary evidence")
        if not primary & CONDITIONAL_ENTRY_EVIDENCE:
            raise ValueError("structural stage requires conditional entry-quality evidence")
        if "response_topology" not in primary:
            raise ValueError("structural stage requires response topology evidence")
        if not primary & SAMPLE_THINNING_EVIDENCE:
            raise ValueError("structural stage requires sample or thinning evidence")
        if stage in {"structural_interaction", "entry_region_selection"}:
            if "neighborhood_stability" not in primary:
                raise ValueError(f"{stage} requires neighborhood evidence")
            if not primary & SIDE_BEHAVIOR_EVIDENCE:
                raise ValueError(f"{stage} requires side-behavior evidence")
        if "after_cost_positive" in roles.promotion_gates:
            raise ValueError("after-cost positivity cannot gate structural discovery")
    elif stage == "exit_geometry":
        if primary != EXIT_PRIMARY:
            raise ValueError("exit_geometry is missing required economic primary evidence")
        if "after_cost_positive" not in roles.promotion_gates:
            raise ValueError("exit_geometry must expose the after-cost promotion gate")
    else:
        if not ROBUSTNESS_PRIMARY <= primary or not primary <= ROBUSTNESS_PRIMARY_ALLOWED:
            raise ValueError("robustness_validation is missing required primary evidence")
        if "after_cost_positive" not in roles.promotion_gates:
            raise ValueError("robustness promotion must expose the after-cost gate")


def _iter_evidence(value: Any) -> list[EvidenceRef]:
    found: list[EvidenceRef] = []
    if isinstance(value, EvidenceRef):
        return [value]
    if isinstance(value, BaseModel):
        for field in type(value).model_fields:
            found.extend(_iter_evidence(getattr(value, field)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_iter_evidence(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_iter_evidence(item))
    return found


def _metric(candidate: dict[str, Any], path: str) -> Any:
    value: Any = candidate
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"canonical metric path {path!r} is unavailable")
        value = value[part]
    return value


def verify_evidence_integrity(
    evidence_refs: list[EvidenceRef],
    *,
    candidate_facts: dict[str, dict[str, Any]],
    prior_assessment_iterations: set[int],
    analysis_path: str | None,
    analysis_root: Path | None = None,
) -> None:
    """Mechanically bind evidence refs to already-authoritative retained facts.

    This performs no scientific interpretation.  It is the strict variant used
    for a v3 stage-closing disposition, where every reference must be presently
    verifiable rather than merely well-shaped.
    """

    for evidence in evidence_refs:
        if evidence.kind == "canonical_metric":
            if evidence.candidate_id not in candidate_facts:
                raise ValueError("canonical evidence references an unknown current candidate")
            _metric(candidate_facts[evidence.candidate_id], evidence.metric_path or "")
        elif evidence.kind == "prior_assessment":
            if evidence.iteration_id not in prior_assessment_iterations:
                raise ValueError("prior assessment evidence references no retained assessment")
        else:
            if evidence.analysis_path != analysis_path or analysis_root is None:
                raise ValueError("analysis evidence does not match a retained iteration artifact")
            try:
                root = analysis_root.resolve(strict=True)
                artifact = Path(evidence.analysis_path or "").resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError("analysis evidence artifact is unavailable") from exc
            if not artifact.is_file() or not artifact.is_relative_to(root):
                raise ValueError("analysis evidence escapes the retained analysis namespace")


def _required_canonical_decimal(candidate: dict[str, Any], field: str) -> Decimal:
    raw = candidate.get(field)
    if raw is None:
        raise ValueError(f"required canonical economic fact {field} is absent")
    try:
        value = Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(f"required canonical economic fact {field} is non-numeric") from exc
    if not value.is_finite():
        raise ValueError(f"required canonical economic fact {field} is non-numeric")
    return value


def _positive_and_consistent(candidate: dict[str, Any]) -> tuple[bool, bool]:
    gross = _required_canonical_decimal(candidate, "gross_pnl")
    fees = _required_canonical_decimal(candidate, "fees_paid")
    net = _required_canonical_decimal(candidate, "net_pnl")
    return_pct = _required_canonical_decimal(candidate, "return_pct")
    profit_factor_raw = candidate.get("profit_factor")
    consistent = gross - fees == net and ((net > 0) == (return_pct > 0))
    if net == 0:
        consistent = consistent and return_pct == 0
    if profit_factor_raw is not None:
        profit_factor = _required_canonical_decimal(candidate, "profit_factor")
        consistent = consistent and (
            (net > 0 and profit_factor > 1)
            or (net == 0 and profit_factor == 1)
            or (net < 0 and profit_factor < 1)
        )
    positive = net > 0 and return_pct > 0
    if profit_factor_raw is not None:
        positive = positive and profit_factor > 1
    elif candidate.get("realised_trade_count", 0) == 0:
        positive = False
    return positive, consistent


def _required_validation_dimensions(kind: str) -> set[str]:
    return {
        "parameter_perturbation": {"parameter_perturbation"},
        "temporal_holdout": {"holdout", "temporal"},
        "regime_split": {"regime"},
        "side_decomposition": {"side"},
        "alternate_window": {"alternate_window"},
        "alternate_ticker": {"alternate_ticker"},
    }[kind]


def enforce_quality_policy(
    policy: ResearchQualityPolicy,
    assessment: ResearchQualityAssessment,
    *,
    phase: str,
    candidate_facts: dict[str, dict[str, Any]],
    prior_iteration: int,
    analysis_path: str | None = None,
) -> None:
    """Mechanically verify a worker-owned assessment without ranking candidates."""

    if assessment.applied_policy_id != policy.policy_id:
        raise ValueError("assessment applied_policy_id differs from immutable session policy")
    binding = phase_binding(policy, phase)
    if assessment.stage.phase != phase or assessment.stage.stage_kind != binding.stage_kind:
        raise ValueError("assessment stage differs from the resolved phase binding")
    validate_metric_roles(assessment)

    subject_refs = set(candidate_facts)
    if assessment.promotion_subject is not None:
        subject_refs.add(assessment.promotion_subject.region_id)
    for comparison in assessment.tradeoff_summary.comparisons:
        if comparison.stage_kind != binding.stage_kind:
            raise ValueError("tradeoff comparison stage differs from assessment stage")
        if (
            comparison.left_subject_ref not in subject_refs
            or comparison.right_subject_ref not in subject_refs
        ):
            raise ValueError("tradeoff comparison references an unknown candidate or region")

    candidate_ids = set(candidate_facts)
    for evidence in _iter_evidence(assessment):
        if evidence.kind == "canonical_metric":
            if evidence.candidate_id not in candidate_ids:
                raise ValueError("canonical evidence references an unknown current candidate")
            _metric(candidate_facts[evidence.candidate_id], evidence.metric_path or "")
        elif evidence.kind == "prior_assessment" and evidence.iteration_id > prior_iteration:
            raise ValueError("prior assessment evidence references a future iteration")
        elif evidence.kind == "analysis_artifact" and evidence.analysis_path != analysis_path:
            raise ValueError("analysis evidence does not match the retained iteration artifact")

    subject = assessment.promotion_subject
    decision = assessment.promotion.decision
    blockers = {blocker.code for blocker in assessment.promotion.blockers}
    strong_claim = decision == "eligible_for_next_stage"
    stage = binding.stage_kind
    economic_claim = assessment.economic_viability.status == "viable"
    if economic_claim and stage not in {"exit_geometry", "robustness_validation"}:
        raise ValueError("economic viability cannot be claimed before exit_geometry")
    if decision == "no_stable_edge" and economic_claim:
        raise ValueError("no_stable_edge cannot simultaneously claim economic viability")
    if (strong_claim or economic_claim) and subject is None:
        raise ValueError("promotion or viability claim requires a promotion_subject")
    if subject is not None:
        referenced = set(subject.representative_candidate_ids) | set(
            subject.neighborhood_candidate_ids
        )
        if subject.baseline_candidate_id is not None:
            referenced.add(subject.baseline_candidate_id)
        if not referenced <= candidate_ids:
            raise ValueError("promotion subject references unknown current candidates")
    if decision == "no_stable_edge":
        return

    if (
        assessment.side_assessment.classification == "two_sided_consistent"
        and assessment.side_assessment.claim_scope != "two_sided"
    ):
        raise ValueError("two_sided_consistent requires two_sided claim scope")
    directional_scopes = {
        "long_dominant": "long_only",
        "short_dominant": "short_only",
        "regime_specific_directional": "regime_specific",
    }
    expected_scope = directional_scopes.get(assessment.side_assessment.classification)
    if expected_scope is not None and assessment.side_assessment.claim_scope != expected_scope:
        raise ValueError("directional side classification has an invalid claim scope")

    if not strong_claim and not economic_claim:
        return
    assert subject is not None
    representatives = subject.representative_candidate_ids
    if not representatives:
        raise ValueError("promotion requires representative candidates")

    if stage in {
        "structural_interaction",
        "entry_region_selection",
        "exit_geometry",
        "robustness_validation",
    }:
        if assessment.structural_promise.neighborhood_stability != "supported":
            raise ValueError("promotion requires neighborhood support")
        if not subject.neighborhood_candidate_ids:
            raise ValueError("promotion requires referenced neighborhood candidates")
        if "isolated_spike" in assessment.information_value.outcomes:
            raise ValueError("isolated spike cannot be promoted")
    if stage == "entry_region_selection":
        structural = assessment.structural_promise
        if structural.status != "promising" or structural.sample_adequacy != "adequate":
            raise ValueError(
                "entry-region promotion requires promising structure and adequate sample"
            )
        if not structural.topology:
            raise ValueError("entry-region promotion requires explicit topology")
        if assessment.side_assessment.classification in {
            "not_applicable",
            "mixed_unresolved",
            "aggregate_masks_side_failure",
        }:
            raise ValueError(
                "entry-region promotion requires a promotable explicit side classification"
            )
        if blockers & {
            "thin_sample",
            "temporal_concentration",
            "regime_concentration",
            "side_masking",
        }:
            raise ValueError("entry-region promotion has a disqualifying structural blocker")

    permitted = set(policy.side_policy.promotable_classifications)
    classification = assessment.side_assessment.classification
    if classification not in permitted:
        raise ValueError("side classification is not permitted for promotion")

    dimensions = {item.dimension: item.status for item in assessment.robustness.dimensions}
    directional = classification in {
        "long_dominant",
        "short_dominant",
        "regime_specific_directional",
    }
    if directional and not (
        dimensions.get("temporal") == "supported" and dimensions.get("regime") == "supported"
    ):
        raise ValueError("directional promotion requires temporal and regime validation")

    validation = policy.validation_policy
    required_now = bool(validation.required_evidence) and (
        stage in {"exit_geometry", "robustness_validation"}
        or (stage == "entry_region_selection" and validation.required_before_entry_region_promotion)
    )
    if required_now:
        for kind in validation.required_evidence:
            choices = _required_validation_dimensions(kind)
            if not any(dimensions.get(choice) == "supported" for choice in choices):
                raise ValueError(f"required validation evidence is missing or failed: {kind}")

    gates = {gate.gate_id: gate for gate in assessment.economic_viability.gate_results}
    declared_gates = set(assessment.stage.metric_roles.promotion_gates)
    if set(gates) - declared_gates:
        raise ValueError("gate results contain a gate absent from stage promotion_gates")
    for gate in gates.values():
        if set(gate.candidate_ids) != set(representatives):
            raise ValueError("promotion gate candidate_ids must equal representative candidates")

    def require_boolean_gate(gate_id: str, expected: bool) -> None:
        gate = gates.get(gate_id)
        observed = {candidate_id: expected for candidate_id in representatives}
        if (
            gate is None
            or gate.source != "hard_invariant"
            or gate.threshold is not None
            or gate.observed_by_candidate != observed
            or gate.status != ("pass" if expected else "fail")
        ):
            raise ValueError(f"hard invariant gate is missing or contradictory: {gate_id}")
        if not expected:
            raise ValueError(f"hard promotion invariant failed: {gate_id}")

    if stage in {
        "structural_interaction",
        "entry_region_selection",
        "exit_geometry",
        "robustness_validation",
    }:
        require_boolean_gate("neighborhood_supported", True)
    require_boolean_gate("side_classification_permitted", classification in permitted)
    if required_now:
        require_boolean_gate("required_validation", True)

    configured_paths: dict[str, tuple[str, Any]] = {
        "minimum_realised_trade_count": (
            "realised_trade_count",
            policy.promotion_thresholds.minimum_realised_trade_count,
        ),
        "minimum_profit_factor": (
            "profit_factor",
            policy.promotion_thresholds.minimum_profit_factor,
        ),
        "minimum_after_cost_return": (
            "return_pct",
            policy.promotion_thresholds.minimum_after_cost_return,
        ),
        "maximum_trade_close_drawdown_magnitude": (
            "max_drawdown",
            policy.promotion_thresholds.maximum_trade_close_drawdown_magnitude,
        ),
        "minimum_long_trade_count": (
            "long.trades",
            policy.promotion_thresholds.minimum_long_trade_count,
        ),
        "minimum_short_trade_count": (
            "short.trades",
            policy.promotion_thresholds.minimum_short_trade_count,
        ),
    }
    structural_thresholds = {
        "minimum_realised_trade_count",
        "minimum_long_trade_count",
        "minimum_short_trade_count",
        "maximum_trade_count_reduction_fraction",
    }
    for gate_id, (path, threshold) in configured_paths.items():
        applies = threshold is not None and (
            stage in {"exit_geometry", "robustness_validation"} or gate_id in structural_thresholds
        )
        if not applies:
            if gate_id in gates and gates[gate_id].source == "configured_threshold":
                raise ValueError(f"absent or stage-inapplicable threshold invented gate {gate_id}")
            continue
        gate = gates.get(gate_id)
        if (
            gate is None
            or gate.source != "configured_threshold"
            or gate.threshold != str(threshold)
        ):
            raise ValueError(f"configured gate is missing or has wrong threshold: {gate_id}")
        observed = {
            candidate_id: _metric(candidate_facts[candidate_id], path)
            for candidate_id in representatives
        }
        if gate_id == "maximum_trade_close_drawdown_magnitude":
            passed = all(
                abs(Decimal(str(value))) <= Decimal(str(threshold)) for value in observed.values()
            )
        else:
            passed = all(
                value is not None and Decimal(str(value)) >= Decimal(str(threshold))
                for value in observed.values()
            )
        expected_observed = {
            key: str(value) if value is not None else None for key, value in observed.items()
        }
        if gate.observed_by_candidate != expected_observed or gate.status != (
            "pass" if passed else "fail"
        ):
            raise ValueError(f"configured gate contradicts canonical metrics: {gate_id}")
        if not passed:
            raise ValueError(f"configured promotion gate failed: {gate_id}")

    reduction_threshold = policy.promotion_thresholds.maximum_trade_count_reduction_fraction
    reduction_gate = gates.get("maximum_trade_count_reduction_fraction")
    if reduction_threshold is None:
        if reduction_gate is not None and reduction_gate.source == "configured_threshold":
            raise ValueError("absent reduction threshold invented a gate")
    elif stage in {"entry_region_selection", "exit_geometry", "robustness_validation"}:
        if subject.baseline_candidate_id is None:
            raise ValueError("trade-count reduction gate requires baseline_candidate_id")
        baseline_count = Decimal(
            str(_metric(candidate_facts[subject.baseline_candidate_id], "realised_trade_count"))
        )
        if baseline_count <= 0:
            raise ValueError("trade-count reduction gate requires positive baseline trade count")
        observed = {
            candidate_id: (
                baseline_count
                - Decimal(str(_metric(candidate_facts[candidate_id], "realised_trade_count")))
            )
            / baseline_count
            for candidate_id in representatives
        }
        if reduction_gate is None or reduction_gate.threshold != str(reduction_threshold):
            raise ValueError("configured trade-count reduction gate is missing")
        expected_observed = {key: str(value) for key, value in observed.items()}
        passed = all(value <= reduction_threshold for value in observed.values())
        if reduction_gate.observed_by_candidate != expected_observed or reduction_gate.status != (
            "pass" if passed else "fail"
        ):
            raise ValueError("trade-count reduction gate contradicts canonical metrics")
        if not passed:
            raise ValueError("configured trade-count reduction gate failed")

    if stage in {"exit_geometry", "robustness_validation"}:
        positive_by_candidate: dict[str, bool] = {}
        consistent_by_candidate: dict[str, bool] = {}
        for candidate_id in representatives:
            positive, consistent = _positive_and_consistent(candidate_facts[candidate_id])
            positive_by_candidate[candidate_id] = positive
            consistent_by_candidate[candidate_id] = consistent
        for gate_id, observed in (
            ("after_cost_positive", positive_by_candidate),
            ("economic_metric_consistency", consistent_by_candidate),
        ):
            gate = gates.get(gate_id)
            if gate is None or gate.source != "hard_invariant" or gate.threshold is not None:
                raise ValueError(f"required hard invariant gate is missing: {gate_id}")
            passed = all(observed.values())
            if gate.observed_by_candidate != observed or gate.status != (
                "pass" if passed else "fail"
            ):
                raise ValueError(f"hard invariant gate contradicts canonical metrics: {gate_id}")
            if not passed:
                raise ValueError(f"hard promotion invariant failed: {gate_id}")
        if (
            assessment.economic_viability.status != "viable"
            or assessment.economic_viability.after_cost_status != "positive"
            or assessment.economic_viability.metric_consistency != "consistent"
        ):
            raise ValueError("economic viability claim contradicts required exit/robustness gates")


def write_contract_schemas(schema_dir: Path) -> None:
    """Write canonical schemas generated from the runtime models."""

    schema_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "research_quality_policy.schema.json": ResearchQualityPolicy.model_json_schema(),
        "research_quality_assessment.schema.json": ResearchQualityAssessment.model_json_schema(),
    }
    for name, schema in payloads.items():
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = schema["properties"]["contract_version"]["const"]
        (schema_dir / name).write_text(
            json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    batch_request = BatchExperimentRequest.model_json_schema()
    batch_request["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    batch_request["$id"] = "bbb_autoresearch_batch_experiment_request.v1"
    batch_request["title"] = "BBB AutoResearch canonical BatchExperimentRequest"
    (schema_dir / "batch_experiment_request.schema.json").write_text(
        json.dumps(batch_request, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    iteration = json.loads((schema_dir / "iteration_result.schema.json").read_text())
    iteration["$id"] = "bbb_autoresearch_iteration.v2"
    iteration["title"] = "BBB AutoResearch iteration result v2"
    iteration["required"].append("research_quality_assessment")
    iteration["properties"]["contract_version"] = {"const": "bbb_autoresearch_iteration.v2"}
    iteration["properties"]["research_quality_assessment"] = {
        "$ref": "research_quality_assessment.schema.json"
    }
    (schema_dir / "iteration_result.v2.schema.json").write_text(
        json.dumps(iteration, ensure_ascii=False, sort_keys=False, indent=2) + "\n",
        encoding="utf-8",
    )

    state = json.loads((schema_dir / "session_state.schema.json").read_text())
    state["$id"] = "bbb_autoresearch_state.v2"
    state["title"] = "BBB AutoResearch session state v2"
    state["required"].extend(
        [
            "research_quality_policy",
            "active_stage_binding",
            "latest_quality_assessment",
            "promotion_history",
        ]
    )
    state["properties"]["contract_version"] = {"const": "bbb_autoresearch_state.v2"}
    state["properties"]["research_quality_policy"] = {"$ref": "research_quality_policy.schema.json"}
    state["properties"]["active_stage_binding"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["phase", "stage_kind"],
        "properties": {
            "phase": {"type": "string", "minLength": 1},
            "stage_kind": {
                "enum": [
                    "descriptive_baseline",
                    "structural_entry",
                    "structural_interaction",
                    "entry_region_selection",
                    "exit_geometry",
                    "robustness_validation",
                ]
            },
        },
    }
    state["properties"]["latest_quality_assessment"] = {
        "oneOf": [
            {"$ref": "research_quality_assessment.schema.json"},
            {"type": "null"},
        ]
    }
    state["properties"]["promotion_history"] = {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["iteration_id", "region_id", "decision", "blockers"],
            "properties": {
                "iteration_id": {"type": "integer", "minimum": 1},
                "region_id": {"type": ["string", "null"], "minLength": 1},
                "decision": {
                    "enum": [
                        "continue_discovery",
                        "investigate_region",
                        "eligible_for_next_stage",
                        "validation_required",
                        "rejected_structurally",
                        "demoted_after_validation",
                        "no_stable_edge",
                    ]
                },
                "blockers": {
                    "type": "array",
                    "items": {
                        "$ref": "research_quality_assessment.schema.json#/$defs/PromotionBlocker"
                    },
                },
            },
        },
    }
    (schema_dir / "session_state.v2.schema.json").write_text(
        json.dumps(state, ensure_ascii=False, sort_keys=False, indent=2) + "\n",
        encoding="utf-8",
    )

    journal = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "bbb_autoresearch_journal.v2",
        "title": "BBB AutoResearch journal event v2",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "session_id",
            "iteration_id",
            "timestamp",
            "baseline_git_sha",
            "research_phase",
            "hypothesis",
            "competing_explanation",
            "experiment_id",
            "candidate_ids",
            "window_policy",
            "strategy_context",
            "parameter_axes",
            "execution_accounting_assumptions",
            "batch_artifact_path",
            "run_ids",
            "market_data_hash",
            "outcome_classification",
            "side_interpretation",
            "risk_assessment",
            "conclusion",
            "next_question",
            "research_quality_assessment",
        ],
        "properties": {
            "contract_version": {"const": "bbb_autoresearch_journal.v2"},
            "session_id": {"type": "string", "minLength": 1},
            "iteration_id": {"type": "integer", "minimum": 1},
            "timestamp": {"type": "string", "format": "date-time"},
            "baseline_git_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "research_phase": {"type": "string", "minLength": 1},
            "hypothesis": {"type": "string", "minLength": 1},
            "competing_explanation": {"type": "array", "items": {"type": "string"}},
            "experiment_id": {"type": ["string", "null"]},
            "candidate_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "window_policy": {"type": ["object", "null"]},
            "strategy_context": {"type": ["object", "null"]},
            "parameter_axes": {"type": "array", "items": {"type": "object"}},
            "execution_accounting_assumptions": {"type": ["object", "null"]},
            "batch_artifact_path": {"type": ["string", "null"]},
            "run_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "market_data_hash": {"type": ["string", "null"]},
            "outcome_classification": {"type": "string"},
            "side_interpretation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["aggregate", "long", "short", "asymmetry"],
                "properties": {
                    key: {"type": "string", "minLength": 1}
                    for key in ("aggregate", "long", "short", "asymmetry")
                },
            },
            "risk_assessment": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "thinning_risk",
                    "temporal_regime_concentration_concern",
                    "other_confounders",
                ],
                "properties": {
                    "thinning_risk": {"type": ["string", "null"], "minLength": 1},
                    "temporal_regime_concentration_concern": {
                        "type": ["string", "null"],
                        "minLength": 1,
                    },
                    "other_confounders": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "conclusion": {"type": "string", "minLength": 1},
            "next_question": {"type": "string", "minLength": 1},
            "research_quality_assessment": {"$ref": "research_quality_assessment.schema.json"},
        },
    }
    (schema_dir / "journal_event.v2.schema.json").write_text(
        json.dumps(journal, ensure_ascii=False, sort_keys=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_contract_schemas(Path(__file__).resolve().parents[1] / "autoresearch" / "schemas")
