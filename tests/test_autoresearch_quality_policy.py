from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.experiments import (
    BatchCandidateRequest,
    BatchCandidateResult,
    BatchExperimentRequest,
    BatchExperimentResult,
    PersistBatchExperiment,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.strategy_instance import DeployableStrategyInstance

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from autoresearch_init import initialize_session  # noqa: E402
from autoresearch_quality_contracts import (  # noqa: E402
    EvidenceRef,
    EXIT_PRIMARY,
    ROBUSTNESS_PRIMARY,
    ResearchQualityAssessment,
    ResearchQualityPolicy,
    enforce_quality_policy,
    write_contract_schemas,
)
from autoresearch_supervisor import (  # noqa: E402
    ContractError,
    _advance_state,
    _journal_event,
    load_json,
    validate_iteration_result,
    validate_state,
)


def _policy(stage: str, **thresholds: object) -> ResearchQualityPolicy:
    values: dict[str, object] = {
        "minimum_realised_trade_count": None,
        "minimum_profit_factor": None,
        "minimum_after_cost_return": None,
        "maximum_trade_close_drawdown_magnitude": None,
        "minimum_long_trade_count": None,
        "minimum_short_trade_count": None,
        "maximum_trade_count_reduction_fraction": None,
    }
    values.update(thresholds)
    return ResearchQualityPolicy.model_validate(
        {
            "contract_version": "bbb_research_quality_policy.v1",
            "policy_id": "policy-1",
            "provenance": {
                "source": "session",
                "references": [],
                "rationale": "resolved test policy",
            },
            "phase_bindings": [{"phase": "test-phase", "stage_kind": stage}],
            "promotion_thresholds": values,
            "side_policy": {
                "promotable_classifications": [
                    "two_sided_consistent",
                    "long_dominant",
                    "short_dominant",
                    "regime_specific_directional",
                ]
            },
            "validation_policy": {
                "required_before_entry_region_promotion": False,
                "required_evidence": [],
            },
        }
    )


def _facts(*, net: str = "100", trades: int = 100, profit_factor: str = "1.20") -> dict[str, dict[str, object]]:
    def candidate(candidate_id: str, candidate_trades: int) -> dict[str, object]:
        positive = net != "-10"
        return {
            "candidate_id": candidate_id,
            "realised_trade_count": candidate_trades,
            "open_position_count": 0,
            "final_equity": "10100" if positive else "9990",
            "gross_pnl": "120" if positive else "10",
            "fees_paid": "20",
            "net_pnl": net,
            "return_pct": "0.01" if positive else "-0.001",
            "win_rate": "0.55",
            "profit_factor": profit_factor if positive else "0.90",
            "max_drawdown": "-0.02",
            "long": {
                "trades": candidate_trades // 2,
                "net_pnl": "70" if positive else "5",
                "return_pct": "0.007" if positive else "0.0005",
                "win_rate": "0.57",
                "profit_factor": "1.3" if positive else "1.05",
            },
            "short": {
                "trades": candidate_trades - candidate_trades // 2,
                "net_pnl": "30" if positive else "-15",
                "return_pct": "0.003" if positive else "-0.0015",
                "win_rate": "0.53",
                "profit_factor": "1.1" if positive else "0.8",
            },
        }

    return {
        "baseline": candidate("baseline", 200),
        "c1": candidate("c1", trades),
        "c2": candidate("c2", trades),
    }


def _roles(stage: str) -> dict[str, object]:
    if stage == "descriptive_baseline":
        return {
            "descriptive": ["net_pnl", "return_pct", "profit_factor", "max_drawdown"],
            "primary": ["realised_trade_count"],
            "secondary": [],
            "promotion_gates": [],
        }
    if stage in {"structural_entry", "structural_interaction", "entry_region_selection"}:
        return {
            "descriptive": ["gross_pnl", "fees_paid"],
            "primary": [
                "baseline_uplift", "response_topology", "neighborhood_stability",
                "realised_trade_count", "win_rate", "long.win_rate", "short.win_rate",
                "thinning",
            ],
            "secondary": ["net_pnl", "return_pct", "profit_factor", "max_drawdown"],
            "promotion_gates": ["neighborhood_supported", "side_classification_permitted"],
        }
    if stage == "exit_geometry":
        return {
            "descriptive": ["gross_pnl", "fees_paid"],
            "primary": sorted(EXIT_PRIMARY),
            "secondary": ["win_rate"],
            "promotion_gates": [
                "after_cost_positive", "economic_metric_consistency",
                "neighborhood_supported", "side_classification_permitted",
            ],
        }
    return {
        "descriptive": ["gross_pnl", "fees_paid"],
        "primary": sorted(ROBUSTNESS_PRIMARY),
        "secondary": ["net_pnl"],
        "promotion_gates": [
            "after_cost_positive", "economic_metric_consistency",
            "neighborhood_supported", "side_classification_permitted",
        ],
    }


def _evidence(candidate_id: str = "c1", metric: str = "net_pnl") -> dict[str, object]:
    return {
        "kind": "canonical_metric",
        "claim_id": f"{candidate_id}-{metric}",
        "candidate_id": candidate_id,
        "metric_path": metric,
        "iteration_id": None,
        "analysis_path": None,
    }


def test_canonical_metric_evidence_rejects_analysis_path() -> None:
    evidence = _evidence()
    evidence["analysis_path"] = "interpretation_analysis/claim.json"

    with pytest.raises(ValidationError, match="canonical_metric evidence has invalid fields"):
        EvidenceRef.model_validate(evidence)


def test_canonical_metric_evidence_rejects_unknown_metric_path() -> None:
    evidence = _evidence(metric="invented.metric")

    with pytest.raises(
        ValidationError, match="canonical_metric evidence requires candidate_id and metric_path"
    ):
        EvidenceRef.model_validate(evidence)


def _assessment(
    stage: str,
    *,
    decision: str = "eligible_for_next_stage",
    net_positive: bool = True,
    topology: str = "broad plateau",
    side: str = "two_sided_consistent",
) -> dict[str, object]:
    strong = decision == "eligible_for_next_stage"
    dimensions = [
        {"dimension": "neighborhood", "status": "supported", "evidence_refs": [], "rationale": "broad support"},
        {"dimension": "temporal", "status": "supported", "evidence_refs": [], "rationale": "stable through time"},
        {"dimension": "regime", "status": "supported", "evidence_refs": [], "rationale": "stable by regime"},
    ]
    gates: list[dict[str, object]] = []
    if strong:
        gates.append(
            {
                "gate_id": "side_classification_permitted",
                "source": "hard_invariant",
                "candidate_ids": ["c1"],
                "threshold": None,
                "observed_by_candidate": {"c1": True},
                "status": "pass",
                "evidence_refs": [_evidence("c1", "long.net_pnl")],
            }
        )
    if strong and stage in {
        "structural_interaction", "entry_region_selection", "exit_geometry",
        "robustness_validation",
    }:
        gates.append(
            {
                "gate_id": "neighborhood_supported",
                "source": "hard_invariant",
                "candidate_ids": ["c1"],
                "threshold": None,
                "observed_by_candidate": {"c1": True},
                "status": "pass",
                "evidence_refs": [_evidence("c1", "realised_trade_count")],
            }
        )
    if stage in {"exit_geometry", "robustness_validation"}:
        gates.extend([
            {
                "gate_id": "after_cost_positive",
                "source": "hard_invariant",
                "candidate_ids": ["c1"],
                "threshold": None,
                "observed_by_candidate": {"c1": net_positive},
                "status": "pass" if net_positive else "fail",
                "evidence_refs": [_evidence("c1", "net_pnl")],
            },
            {
                "gate_id": "economic_metric_consistency",
                "source": "hard_invariant",
                "candidate_ids": ["c1"],
                "threshold": None,
                "observed_by_candidate": {"c1": True},
                "status": "pass",
                "evidence_refs": [_evidence("c1", "gross_pnl")],
            },
        ])
    scopes = {
        "two_sided_consistent": "two_sided",
        "long_dominant": "long_only",
        "short_dominant": "short_only",
        "regime_specific_directional": "regime_specific",
        "aggregate_masks_side_failure": "unresolved",
        "mixed_unresolved": "unresolved",
        "not_applicable": "not_applicable",
    }
    return {
        "contract_version": "bbb_research_quality_assessment.v1",
        "applied_policy_id": "policy-1",
        "stage": {"phase": "test-phase", "stage_kind": stage, "metric_roles": _roles(stage)},
        "promotion_subject": (
            {
                "region_id": "region-1",
                "baseline_candidate_id": "baseline",
                "representative_candidate_ids": ["c1"],
                "neighborhood_candidate_ids": ["c2"],
            }
            if strong or decision == "investigate_region"
            else None
        ),
        "information_value": {
            "status": "informative",
            "outcomes": ["broad_optimum"] if topology != "isolated spike" else ["isolated_spike"],
            "rationale": "response topology increased knowledge",
            "evidence_refs": [],
        },
        "structural_promise": {
            "status": "promising",
            "baseline_comparison": "improved",
            "topology": topology,
            "neighborhood_stability": "supported",
            "sample_adequacy": "adequate",
            "economic_direction": "degraded" if not net_positive else "improved",
            "market_state_interpretation": "interpretable region",
            "competing_explanation": "possible concentration",
            "rationale": "broad stable response",
        },
        "economic_viability": {
            "status": "viable" if stage in {"exit_geometry", "robustness_validation"} and net_positive else "not_applicable",
            "after_cost_status": "positive" if stage in {"exit_geometry", "robustness_validation"} and net_positive else "negative",
            "metric_consistency": "consistent" if stage in {"exit_geometry", "robustness_validation"} else "not_assessed",
            "gate_results": gates,
            "rationale": "stage-correct economic interpretation",
        },
        "robustness": {
            "status": "supported" if stage == "robustness_validation" else "not_tested",
            "dimensions": dimensions,
            "rationale": "explicit robustness evidence",
        },
        "side_assessment": {
            "classification": side,
            "claim_scope": scopes[side],
            "rationale": "explicit side scope",
        },
        "tradeoff_summary": {"comparisons": [], "rationale": "no scalar winner"},
        "promotion": {"decision": decision, "blockers": [], "rationale": "policy disposition"},
    }


def _enforce(policy: ResearchQualityPolicy, assessment: dict[str, object], facts: dict[str, dict[str, object]]) -> None:
    enforce_quality_policy(
        policy,
        ResearchQualityAssessment.model_validate(assessment),
        phase="test-phase",
        candidate_facts=facts,
        prior_iteration=0,
        analysis_path=None,
    )


def test_losing_but_informative_structural_sweep_is_retained() -> None:
    assessment = _assessment("structural_entry", decision="continue_discovery", net_positive=False)
    _enforce(_policy("structural_entry"), assessment, _facts(net="-10", profit_factor="0.90"))
    assert assessment["information_value"]["status"] == "informative"
    assert assessment["economic_viability"]["after_cost_status"] == "negative"


def test_structurally_strong_negative_symmetric_region_can_enter_exit_geometry() -> None:
    assessment = _assessment("entry_region_selection", net_positive=False)
    _enforce(_policy("entry_region_selection"), assessment, _facts(net="-10", profit_factor="0.90"))
    assert assessment["promotion"]["decision"] == "eligible_for_next_stage"


def test_profitable_isolated_spike_and_unsupported_neighborhood_cannot_promote() -> None:
    spike = _assessment("entry_region_selection", topology="isolated spike")
    with pytest.raises(ValueError, match="isolated spike"):
        _enforce(_policy("entry_region_selection"), spike, _facts())
    unsupported = _assessment("entry_region_selection")
    unsupported["structural_promise"]["neighborhood_stability"] = "unsupported"
    with pytest.raises(ValueError, match="neighborhood"):
        _enforce(_policy("entry_region_selection"), unsupported, _facts())


def test_exit_geometry_is_first_economic_primary_stage_and_requires_positive_economics() -> None:
    structural = _assessment("structural_entry", decision="continue_discovery", net_positive=False)
    assert "net_pnl" in structural["stage"]["metric_roles"]["secondary"]
    assert "net_pnl" not in structural["stage"]["metric_roles"]["primary"]
    exit_assessment = _assessment("exit_geometry", net_positive=False)
    with pytest.raises(ValueError, match="after_cost_positive"):
        _enforce(_policy("exit_geometry"), exit_assessment, _facts(net="-10", profit_factor="0.90"))
    assert "net_pnl" in exit_assessment["stage"]["metric_roles"]["primary"]


def test_phase_a_economics_are_descriptive_and_cannot_be_primary() -> None:
    baseline = _assessment("descriptive_baseline", decision="continue_discovery", net_positive=False)
    _enforce(_policy("descriptive_baseline"), baseline, _facts(net="-10", profit_factor="0.90"))
    baseline["stage"]["metric_roles"]["descriptive"].remove("profit_factor")
    baseline["stage"]["metric_roles"]["primary"] = ["profit_factor"]
    with pytest.raises(ValueError, match="control sample adequacy"):
        _enforce(_policy("descriptive_baseline"), baseline, _facts())


def test_semantically_incomplete_stage_metric_roles_fail_closed() -> None:
    baseline = _assessment("descriptive_baseline", decision="continue_discovery")
    baseline["stage"]["metric_roles"]["primary"] = ["win_rate"]
    with pytest.raises(ValueError, match="control sample adequacy"):
        _enforce(_policy("descriptive_baseline"), baseline, _facts())

    entry = _assessment("structural_entry", decision="continue_discovery")
    entry["stage"]["metric_roles"]["primary"] = ["response_topology"]
    with pytest.raises(ValueError, match="conditional entry-quality"):
        _enforce(_policy("structural_entry"), entry, _facts())

    no_topology = _assessment("structural_entry", decision="continue_discovery")
    no_topology["stage"]["metric_roles"]["primary"] = [
        "baseline_uplift", "realised_trade_count"
    ]
    with pytest.raises(ValueError, match="response topology"):
        _enforce(_policy("structural_entry"), no_topology, _facts())

    no_sample = _assessment("structural_entry", decision="continue_discovery")
    no_sample["stage"]["metric_roles"]["primary"] = [
        "baseline_uplift", "response_topology"
    ]
    with pytest.raises(ValueError, match="sample or thinning"):
        _enforce(_policy("structural_entry"), no_sample, _facts())

    interaction = _assessment("structural_interaction", decision="continue_discovery")
    interaction["stage"]["metric_roles"]["primary"].remove("neighborhood_stability")
    with pytest.raises(ValueError, match="neighborhood evidence"):
        _enforce(_policy("structural_interaction"), interaction, _facts())

    no_side = _assessment("structural_interaction", decision="continue_discovery")
    no_side["stage"]["metric_roles"]["primary"].remove("long.win_rate")
    no_side["stage"]["metric_roles"]["primary"].remove("short.win_rate")
    with pytest.raises(ValueError, match="side-behavior evidence"):
        _enforce(_policy("structural_interaction"), no_side, _facts())


def test_configured_minimum_trade_count_is_mechanical_and_null_invents_no_gate() -> None:
    assessment = _assessment("entry_region_selection")
    configured_gate = {
        "gate_id": "minimum_realised_trade_count",
        "source": "configured_threshold",
        "candidate_ids": ["c1"],
        "threshold": "101",
        "observed_by_candidate": {"c1": "100"},
        "status": "fail",
        "evidence_refs": [_evidence("c1", "realised_trade_count")],
    }
    assessment["economic_viability"]["gate_results"].append(configured_gate)
    assessment["stage"]["metric_roles"]["promotion_gates"].append(
        "minimum_realised_trade_count"
    )
    with pytest.raises(ValueError, match="configured promotion gate failed"):
        _enforce(_policy("entry_region_selection", minimum_realised_trade_count=101), assessment, _facts())

    no_threshold = _assessment("entry_region_selection")
    _enforce(_policy("entry_region_selection"), no_threshold, _facts())
    invented = copy.deepcopy(no_threshold)
    invented["economic_viability"]["gate_results"].append(configured_gate)
    invented["stage"]["metric_roles"]["promotion_gates"].append(
        "minimum_realised_trade_count"
    )
    with pytest.raises(ValueError, match="invented gate"):
        _enforce(_policy("entry_region_selection"), invented, _facts())


def test_directional_result_is_narrowly_classified_and_requires_validation() -> None:
    assessment = _assessment("entry_region_selection", side="long_dominant")
    assessment["robustness"]["dimensions"] = []
    with pytest.raises(ValueError, match="directional promotion"):
        _enforce(_policy("entry_region_selection"), assessment, _facts())
    assert assessment["side_assessment"]["claim_scope"] == "long_only"


def test_failed_validation_can_demote_and_no_stable_edge_is_valid() -> None:
    demoted = _assessment("robustness_validation", decision="demoted_after_validation")
    strong_robustness = _assessment("robustness_validation")
    demoted["promotion_subject"] = strong_robustness["promotion_subject"]
    demoted["economic_viability"]["gate_results"] = strong_robustness[
        "economic_viability"
    ]["gate_results"]
    demoted["robustness"]["status"] = "failed"
    demoted["robustness"]["dimensions"][0]["status"] = "failed"
    demoted["promotion"]["blockers"] = [
        {"code": "validation_failed", "gate_id": "required_validation", "message": "holdout failed", "evidence_refs": []}
    ]
    _enforce(_policy("robustness_validation"), demoted, _facts())

    no_edge = _assessment("entry_region_selection", decision="no_stable_edge")
    no_edge["structural_promise"]["status"] = "not_promising"
    _enforce(_policy("entry_region_selection"), no_edge, _facts(net="-10"))


def test_pareto_tradeoff_does_not_choose_winner() -> None:
    assessment = _assessment("structural_entry", decision="investigate_region")
    assessment["tradeoff_summary"]["comparisons"] = [
        {
            "left_subject_ref": "c1",
            "right_subject_ref": "c2",
            "stage_kind": "structural_entry",
            "dimensions": [
                {"dimension": "profitability", "assessment": "left_better", "evidence_refs": []},
                {"dimension": "sample_size", "assessment": "right_better", "evidence_refs": []},
                {"dimension": "neighborhood_stability", "assessment": "right_better", "evidence_refs": []},
            ],
            "relation": "tradeoff",
        }
    ]
    _enforce(_policy("structural_entry"), assessment, _facts(trades=40, profit_factor="1.35"))
    assert "winner" not in assessment["tradeoff_summary"]
    assert assessment["promotion"]["decision"] == "investigate_region"


def test_lower_pf_broad_region_remains_investigable() -> None:
    assessment = _assessment("structural_entry", decision="investigate_region")
    assessment["tradeoff_summary"]["comparisons"] = [
        {
            "left_subject_ref": "c1",
            "right_subject_ref": "c2",
            "stage_kind": "structural_entry",
            "dimensions": [
                {"dimension": "profitability", "assessment": "right_better", "evidence_refs": []},
                {"dimension": "sample_size", "assessment": "left_better", "evidence_refs": []},
                {"dimension": "neighborhood_stability", "assessment": "left_better", "evidence_refs": []},
            ],
            "relation": "tradeoff",
        }
    ]
    _enforce(_policy("structural_entry"), assessment, _facts(profit_factor="1.18"))
    assert assessment["promotion"]["decision"] == "investigate_region"


def test_profitable_aggregate_with_losing_short_is_directional_not_universal() -> None:
    facts = _facts()
    facts["c1"]["short"]["net_pnl"] = "-10"
    facts["c1"]["short"]["return_pct"] = "-0.001"
    facts["c1"]["short"]["profit_factor"] = "0.8"
    assessment = _assessment("entry_region_selection", side="long_dominant")
    _enforce(_policy("entry_region_selection"), assessment, facts)
    assert assessment["side_assessment"]["claim_scope"] == "long_only"
    assert assessment["side_assessment"]["classification"] != "two_sided_consistent"


def test_positive_exit_geometry_with_consistent_canonical_facts_can_promote() -> None:
    assessment = _assessment("exit_geometry")
    _enforce(_policy("exit_geometry"), assessment, _facts())
    assert assessment["economic_viability"]["status"] == "viable"


def test_non_numeric_required_economic_fact_fails_as_validation_error() -> None:
    facts = _facts()
    facts["c1"]["fees_paid"] = "not-a-decimal"
    with pytest.raises(ValueError, match="fees_paid is non-numeric"):
        _enforce(_policy("exit_geometry"), _assessment("exit_geometry"), facts)


def test_inconsistent_pf_and_required_validation_fail_closed() -> None:
    inconsistent = _assessment("exit_geometry")
    with pytest.raises(ValueError, match="canonical metrics"):
        _enforce(_policy("exit_geometry"), inconsistent, _facts(profit_factor="0.90"))

    policy_value = _policy("entry_region_selection").model_dump(mode="json")
    policy_value["validation_policy"] = {
        "required_before_entry_region_promotion": True,
        "required_evidence": ["temporal_holdout"],
    }
    assessment = _assessment("entry_region_selection")
    assessment["robustness"]["dimensions"] = []
    with pytest.raises(ValueError, match="required validation"):
        _enforce(ResearchQualityPolicy.model_validate(policy_value), assessment, _facts())


def test_viability_claim_is_enforced_even_without_next_stage_decision() -> None:
    assessment = _assessment("exit_geometry", decision="investigate_region", net_positive=False)
    assessment["promotion_subject"] = {
        "region_id": "region-1",
        "baseline_candidate_id": "baseline",
        "representative_candidate_ids": ["c1"],
        "neighborhood_candidate_ids": ["c2"],
    }
    assessment["economic_viability"]["status"] = "viable"
    assessment["economic_viability"]["gate_results"] = _assessment(
        "exit_geometry", net_positive=False
    )["economic_viability"]["gate_results"]
    with pytest.raises(ValueError, match="after_cost_positive"):
        _enforce(_policy("exit_geometry"), assessment, _facts(net="-10", profit_factor="0.90"))

    early = _assessment("structural_entry", decision="investigate_region")
    early["economic_viability"]["status"] = "viable"
    with pytest.raises(ValueError, match="before exit_geometry"):
        _enforce(_policy("structural_entry"), early, _facts())


def test_unknown_phase_binding_and_side_masking_fail_closed() -> None:
    assessment = ResearchQualityAssessment.model_validate(_assessment("entry_region_selection"))
    with pytest.raises(ValueError, match="binding"):
        enforce_quality_policy(
            _policy("entry_region_selection"),
            assessment,
            phase="unknown-phase",
            candidate_facts=_facts(),
            prior_iteration=0,
        )
    masked = _assessment("entry_region_selection", side="aggregate_masks_side_failure")
    with pytest.raises(ValueError, match="promotable explicit side"):
        _enforce(_policy("entry_region_selection"), masked, _facts())


def _repo(tmp_path: Path, policy: ResearchQualityPolicy | None) -> tuple[Path, Path]:
    (tmp_path / ".claude/skills/ema-anchor-edge-research").mkdir(parents=True)
    (tmp_path / ".claude/skills/ema-anchor-edge-research/SKILL.md").write_text("policy")
    template: dict[str, object] = {
        "research_program": "ema-anchor-edge-research",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "phase": "test-phase" if policy is not None else "baseline",
        "budgets": {"max_consecutive_agent_failures": 3},
    }
    if policy is not None:
        template["research_quality_policy"] = policy.model_dump(mode="json")
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    return tmp_path, initialize_session("s1", template_path, tmp_path)


def _artifact(
    tmp_path: Path, *, net: str = "100", null_economic_field: str | None = None
) -> Path:
    request = BatchExperimentRequest(
        experiment_id="exp-1",
        strategy_id="ema_pullback",
        range=ExplicitRange(from_ms=0, to_ms=300_000),
        candidates=tuple(
            BatchCandidateRequest(
                candidate_id=candidate_id,
                strategy=DeployableStrategyInstance(
                    enabled=True,
                    strategy_id="ema_pullback",
                    ticker="BTCUSDT.P",
                    base_timeframe="5m",
                    raw_spec={"anchor": {"period": 200}},
                ),
                managed_policy_enabled=False,
            )
            for candidate_id in ("baseline", "c1", "c2")
        ),
    )
    facts = _facts(net=net)

    def candidate_result(candidate_id: str, value: dict[str, object]) -> BatchCandidateResult:
        economic = {
            "gross_pnl": value["gross_pnl"],
            "fees_paid": value["fees_paid"],
            "net_pnl": value["net_pnl"],
            "return_pct": value["return_pct"],
        }
        if candidate_id == "c1" and null_economic_field is not None:
            economic[null_economic_field] = None
        return BatchCandidateResult(
            candidate_id=candidate_id,
            run_id=f"run-{candidate_id}",
            instance_id=f"instance-{candidate_id}",
            status="completed",
            artifact_path=f"/runs/{candidate_id}",
            realised_trade_count=value["realised_trade_count"],
            open_position_count=0,
            final_equity=value["final_equity"],
            gross_pnl=economic["gross_pnl"],
            fees_paid=economic["fees_paid"],
            net_pnl=economic["net_pnl"],
            market_data_hash="market-hash",
            return_pct=economic["return_pct"],
            win_rate=value["win_rate"],
            profit_factor=value["profit_factor"],
            max_drawdown=value["max_drawdown"],
            long=value["long"],
            short=value["short"],
        )

    candidates = tuple(
        candidate_result(candidate_id, value) for candidate_id, value in facts.items()
    )
    result = BatchExperimentResult(
        experiment_id="exp-1",
        status="completed",
        candidate_count=3,
        completed_count=3,
        failed_count=0,
        candidates=candidates,
    )
    return Path(PersistBatchExperiment(FilesystemArtifactStore(tmp_path / "artifacts")).execute(request, result).artifact_path)


def _iteration(artifact: Path, assessment: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": "bbb_autoresearch_iteration.v2",
        "session_id": "s1",
        "iteration_id": 1,
        "status": "completed",
        "phase": "test-phase",
        "hypothesis": "stable structural region",
        "market_property_proxy": "test proxy",
        "experiment": {
            "kind": "batch",
            "experiment_id": "exp-1",
            "axes": [],
            "candidate_ids": ["baseline", "c1", "c2"],
            "candidate_count": 3,
            "window_policy": {"range_policy": "explicit_range"},
            "strategy_context": {"strategy_id": "ema_pullback"},
            "execution_accounting_assumptions": {},
        },
        "execution_result": {
            "batch_artifact_path": str(artifact),
            "run_ids": ["run-baseline", "run-c1", "run-c2"],
            "market_data_hash": "market-hash",
            "completed_candidates": 3,
            "failed_candidates": 0,
            "analysis_path": None,
        },
        "observed_response": {
            "topology": "broad plateau",
            "structural_dimensions": ["x"],
            "tested_ranges": [],
            "promising_regions": [{"region_id": "region-1"}],
            "rejected_regions": [],
        },
        "side_interpretation": {"aggregate": "positive", "long": "positive", "short": "positive", "asymmetry": "balanced"},
        "risk_assessment": {"thinning_risk": None, "temporal_regime_concentration_concern": None, "other_confounders": []},
        "conclusion": "broad stable region",
        "next_discriminating_question": "test exit geometry",
        "proposed_next_experiment": {"kind": "exit_geometry", "reason": "test conversion"},
        "hard_stop_reason": None,
        "research_quality_assessment": assessment,
    }


def test_v2_supervisor_validates_and_durably_projects_full_assessment(tmp_path: Path) -> None:
    policy = _policy("entry_region_selection")
    _, root = _repo(tmp_path / "repo", policy)
    state = load_json(root / "state.json")
    artifact = _artifact(tmp_path)
    result = _iteration(artifact, _assessment("entry_region_selection", net_positive=False))
    validate_iteration_result(result, state, artifacts_root=tmp_path / "artifacts")
    updated = _advance_state(state, result)
    validate_state(updated)
    event = _journal_event(state, result)
    assert state["contract_version"] == "bbb_autoresearch_state.v2"
    assert event["contract_version"] == "bbb_autoresearch_journal.v2"
    assert event["research_quality_assessment"] == result["research_quality_assessment"]
    assert updated["latest_quality_assessment"] == result["research_quality_assessment"]
    assert updated["promotion_history"][0]["decision"] == "eligible_for_next_stage"


@pytest.mark.parametrize("field", ["gross_pnl", "fees_paid", "net_pnl"])
def test_missing_optional_canonical_economic_fact_rejects_promotion_cleanly(
    tmp_path: Path, field: str
) -> None:
    policy = _policy("exit_geometry")
    _, root = _repo(tmp_path / "repo", policy)
    state = load_json(root / "state.json")
    artifact = _artifact(tmp_path, null_economic_field=field)
    result = _iteration(artifact, _assessment("exit_geometry"))

    with pytest.raises(
        ContractError, match=rf"required canonical economic fact {field} is absent"
    ):
        validate_iteration_result(result, state, artifacts_root=tmp_path / "artifacts")


def test_v1_session_rejects_v2_iteration_and_v2_rejects_v1(tmp_path: Path) -> None:
    _, legacy_root = _repo(tmp_path / "legacy", None)
    legacy = load_json(legacy_root / "state.json")
    assert legacy["contract_version"] == "bbb_autoresearch_state.v1"
    with pytest.raises(ContractError, match="bbb_autoresearch_iteration.v1"):
        validate_iteration_result({"contract_version": "bbb_autoresearch_iteration.v2"}, legacy)

    _, quality_root = _repo(tmp_path / "quality", _policy("entry_region_selection"))
    quality = load_json(quality_root / "state.json")
    with pytest.raises(ContractError, match="bbb_autoresearch_iteration.v2"):
        validate_iteration_result({"contract_version": "bbb_autoresearch_iteration.v1"}, quality)


def test_exact_quality_schemas_are_generated_from_runtime_models(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "autoresearch" / "schemas"
    for name in ("iteration_result.schema.json", "session_state.schema.json"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    write_contract_schemas(tmp_path)
    for name in (
        "research_quality_policy.schema.json",
        "research_quality_assessment.schema.json",
        "iteration_result.v2.schema.json",
        "session_state.v2.schema.json",
        "journal_event.v2.schema.json",
    ):
        assert (tmp_path / name).read_bytes() == (source / name).read_bytes()


def test_contract_rejects_extra_fields_duplicate_bindings_and_numeric_decimal() -> None:
    value = _policy("structural_entry").model_dump(mode="json")
    value["unexpected"] = True
    with pytest.raises(ValidationError):
        ResearchQualityPolicy.model_validate(value)
    duplicate = _policy("structural_entry").model_dump(mode="json")
    duplicate["phase_bindings"].append(copy.deepcopy(duplicate["phase_bindings"][0]))
    with pytest.raises(ValidationError, match="unique"):
        ResearchQualityPolicy.model_validate(duplicate)
    numeric = _policy("structural_entry").model_dump(mode="json")
    numeric["promotion_thresholds"]["minimum_profit_factor"] = 1.2
    with pytest.raises(ValidationError, match="strings"):
        ResearchQualityPolicy.model_validate(numeric)
