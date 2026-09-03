from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from research_service.application.experiments import BatchExperimentRequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from autoresearch_stage_contracts import (
    STAGE_PHASES,
    StageContractError,
    canonical_sha256,
    geometry_references,
    reference_strategy,
    validate_disposition,
    validate_stage_contract,
    validate_stage_context,
    validate_stage_request,
)
import autoresearch_init
from autoresearch_init import initialize_session
from autoresearch_supervisor import render_interpretation_prompt, render_planning_prompt
from autoresearch_quality_contracts import EvidenceRef, verify_evidence_integrity


def _strategy() -> dict:
    return {
        "enabled": True,
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {
            "anchor_stack": {
                "fast": {"period": 100, "source": "close", "timeframe": "base"},
                "anchor": {"period": 200, "source": "close", "timeframe": "base"},
                "slow": {"period": 500, "source": "close", "timeframe": "base"},
            },
            "components": {
                "direction": "ema_anchor_stack_trend",
                "trigger": {"component_id": "touch_anchor"},
                "blockers": [],
            },
            "setups": [],
            "contexts": {},
            "trade_sides": ["long", "short"],
            "trade_management": {
                "exit_policy": {
                    "always_on": {
                        "exits": [
                            {
                                "component_id": "atr_stop_loss",
                                "instance_id": "sl",
                                "exit_kind": "stop_loss",
                                "distance": {"period": 14, "timeframe": "base", "multiplier": 2},
                            },
                            {
                                "component_id": "atr_take_profit",
                                "instance_id": "tp",
                                "exit_kind": "take_profit",
                                "distance": {"period": 14, "timeframe": "base", "multiplier": 2},
                            },
                        ]
                    },
                    "profiles": {
                        "aligned": {"exits": []},
                        "countertrend": {"exits": []},
                        "neutral": {"exits": []},
                    },
                },
                "exit_management": {},
            },
        },
    }


def _contract() -> dict:
    strategy = _strategy()
    contract = {
        "contract_version": "bbb_autoresearch_stage_contract.v1",
        "programme": "EMA_ANCHOR_A_TO_B",
        "starting_strategy": {
            "source_path": "operator.json",
            "source_sha256": "1" * 64,
            "resolved_sha256": canonical_sha256(strategy),
            "strategy": strategy,
        },
        "semantic_bindings": [
            {
                "dimension": "symmetric_measurement_geometry",
                "targets": [
                    {
                        "component_role": "exits",
                        "component_id": "atr_stop_loss",
                        "instance_id": "sl",
                        "parameter_name": "distance.multiplier",
                        "params_storage": "structural",
                        "fixed_parameters": {},
                    },
                    {
                        "component_role": "exits",
                        "component_id": "atr_take_profit",
                        "instance_id": "tp",
                        "parameter_name": "distance.multiplier",
                        "params_storage": "structural",
                        "fixed_parameters": {},
                    },
                ],
            },
            {
                "dimension": "anchor_stack_width",
                "targets": [
                    {
                        "component_role": "setup",
                        "component_id": "anchor_stack_width_setup",
                        "instance_id": "stage-width",
                        "parameter_name": "min_current_width_atr",
                        "params_storage": "nested",
                        "fixed_parameters": {
                            "atr_timeframe": "base",
                            "atr_period": 14,
                            "min_recent_width_atr": 4.0,
                            "width_lookback_bars": 80,
                        },
                    }
                ],
            },
            {
                "dimension": "untouched_anchor_lookback",
                "targets": [
                    {
                        "component_role": "setup",
                        "component_id": "untouched_anchor_setup",
                        "instance_id": "stage-lookback",
                        "parameter_name": "lookback",
                        "params_storage": "flat",
                        "fixed_parameters": {"active_bars": 3},
                    }
                ],
            },
        ],
        "measurement_geometries": [
            {"geometry_id": "A-2", "distance": 2},
            {"geometry_id": "A-3", "distance": 3},
            {"geometry_id": "A-4", "distance": 4},
        ],
    }
    contract["geometry_references"] = geometry_references(contract)
    return contract


def _state(stage: str = "A_BASELINE") -> dict:
    refs = [] if stage == "A_BASELINE" else [{"geometry_id": "A-2"}]
    dispositions = []
    if stage != "A_BASELINE":
        dispositions.append(
            {
                "iteration_id": 1,
                "disposition": {
                    "stage": "A_BASELINE",
                    "status": "characterized",
                    "evidence": [_evidence(1)],
                },
            }
        )
    stage_kind = {
        "A_BASELINE": "descriptive_baseline",
        "B1_WIDTH": "structural_entry",
        "B2_LOOKBACK": "structural_entry",
        "B3_WIDTH_X_LOOKBACK": "structural_interaction",
    }[stage]
    return {
        "active_stage": stage,
        "active_stage_binding": {"phase": STAGE_PHASES[stage], "stage_kind": stage_kind},
        "stage_contract": _contract(),
        "phase_a_references": refs,
        "stage_dispositions": dispositions,
    }


def _plan(state: dict, geometry_id: str = "A-2") -> dict:
    reference = reference_strategy(state, geometry_id)
    required = [
        entry["iteration_id"]
        for entry in state["stage_dispositions"]
        if entry["disposition"]["status"] != "in_progress"
    ]
    dimensions = {
        "A_BASELINE": ["symmetric_measurement_geometry"],
        "B1_WIDTH": ["anchor_stack_width"],
        "B2_LOOKBACK": ["untouched_anchor_lookback"],
        "B3_WIDTH_X_LOOKBACK": ["anchor_stack_width", "untouched_anchor_lookback"],
    }[state["active_stage"]]
    return {
        "stage_context": {
            "active_stage": state["active_stage"],
            "starting_strategy_sha256": state["stage_contract"]["starting_strategy"][
                "resolved_sha256"
            ],
            "geometry_id": geometry_id,
            "reference_strategy_sha256": canonical_sha256(reference),
            "allowed_semantic_dimensions": dimensions,
            "prerequisite_disposition_refs": required,
        }
    }


def _evidence(iteration_id: int) -> dict:
    return {
        "kind": "prior_assessment",
        "claim_id": f"stage-{iteration_id}",
        "candidate_id": None,
        "metric_path": None,
        "iteration_id": iteration_id,
        "analysis_path": None,
    }


def _request(strategy: dict, *more: dict) -> BatchExperimentRequest:
    candidates = [
        {"candidate_id": f"c{i}", "strategy": item} for i, item in enumerate((strategy, *more), 1)
    ]
    return BatchExperimentRequest.model_validate(
        {
            "experiment_id": "exp",
            "strategy_id": "ema_pullback",
            "range_policy": "full_available",
            "candidates": candidates,
        }
    )


def test_stage_contract_rejects_duplicate_geometry_and_unknown_dimension() -> None:
    contract = _contract()
    validate_stage_contract(contract)
    contract["measurement_geometries"][1]["geometry_id"] = "A-2"
    with pytest.raises(StageContractError, match="unique"):
        validate_stage_contract(contract)
    contract = _contract()
    contract["semantic_bindings"][0]["dimension"] = "json_path"
    with pytest.raises(StageContractError):
        validate_stage_contract(contract)


def test_phase_a_accepts_one_configured_symmetric_geometry_only() -> None:
    state = _state()
    strategy = reference_strategy(state, "A-2")
    validate_stage_request(_request(strategy), _plan(state), state)
    asymmetric = copy.deepcopy(strategy)
    asymmetric["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"][0]["distance"][
        "multiplier"
    ] = 9
    with pytest.raises(StageContractError):
        validate_stage_request(_request(asymmetric), _plan(state), state)
    with pytest.raises(StageContractError, match="exactly one"):
        validate_stage_request(_request(strategy, strategy), _plan(state), state)


def test_b1_allows_only_width_and_preserves_identity_geometry() -> None:
    state = _state("B1_WIDTH")
    candidate = reference_strategy(state, "A-2")
    candidate["raw_spec"]["setups"].append(
        {
            "component_id": "anchor_stack_width_setup",
            "instance_id": "stage-width",
            "params": {
                "atr_timeframe": "base",
                "atr_period": 14,
                "min_current_width_atr": 2.5,
                "min_recent_width_atr": 4.0,
                "width_lookback_bars": 80,
            },
        }
    )
    validate_stage_request(_request(candidate), _plan(state), state)
    candidate["ticker"] = "ETHUSDT.P"
    with pytest.raises(StageContractError, match="outside"):
        validate_stage_request(_request(candidate), _plan(state), state)

    fixed_mutation = reference_strategy(state, "A-2")
    fixed_mutation["raw_spec"]["setups"].append(
        {
            "component_id": "anchor_stack_width_setup",
            "instance_id": "stage-width",
            "params": {
                "atr_timeframe": "base",
                "atr_period": 99,
                "min_current_width_atr": 2.5,
                "min_recent_width_atr": 4.0,
                "width_lookback_bars": 80,
            },
        }
    )
    with pytest.raises(StageContractError, match="fixed fields"):
        validate_stage_request(_request(fixed_mutation), _plan(state), state)


def test_component_array_reordering_is_not_a_semantic_mutation() -> None:
    state = _state("B1_WIDTH")
    candidate = reference_strategy(state, "A-2")
    candidate["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"].reverse()
    candidate["raw_spec"]["setups"].append(
        {
            "component_id": "anchor_stack_width_setup",
            "instance_id": "stage-width",
            "params": {
                "atr_timeframe": "base",
                "atr_period": 14,
                "min_current_width_atr": 3.0,
                "min_recent_width_atr": 4.0,
                "width_lookback_bars": 80,
            },
        }
    )
    validate_stage_request(_request(candidate), _plan(state), state)


def test_b2_rejects_width_leak_and_b3_requires_durable_prerequisites() -> None:
    state = _state("B2_LOOKBACK")
    state["stage_dispositions"].append(
        {
            "iteration_id": 2,
            "disposition": {
                "stage": "B1_WIDTH",
                "status": "terminally_rejected",
                "evidence": [_evidence(2)],
            },
        }
    )
    candidate = reference_strategy(state, "A-2")
    candidate["raw_spec"]["setups"].append(
        {
            "component_id": "untouched_anchor_setup",
            "instance_id": "stage-lookback",
            "lookback": 50,
            "active_bars": 3,
        }
    )
    validate_stage_request(_request(candidate), _plan(state), state)
    candidate["raw_spec"]["setups"].append(
        {
            "component_id": "anchor_stack_width_setup",
            "instance_id": "stage-width",
            "params": {
                "atr_timeframe": "base",
                "atr_period": 14,
                "min_current_width_atr": 2.0,
                "min_recent_width_atr": 4.0,
                "width_lookback_bars": 80,
            },
        }
    )
    with pytest.raises(StageContractError, match="outside"):
        validate_stage_request(_request(candidate), _plan(state), state)
    state["active_stage"] = "B3_WIDTH_X_LOOKBACK"
    plan = _plan(state)
    plan["stage_context"]["prerequisite_disposition_refs"] = [1, 2, 99]
    with pytest.raises(StageContractError, match="prerequisite"):
        validate_stage_context(plan["stage_context"], state)


def test_closing_disposition_requires_evidence() -> None:
    with pytest.raises(StageContractError, match="requires evidence"):
        validate_disposition(
            {"stage": "B1_WIDTH", "status": "characterized", "evidence": []}, "B1_WIDTH"
        )


def test_stage_closure_evidence_must_resolve_to_retained_authority(tmp_path: Path) -> None:
    analysis_root = tmp_path / "interpretation_analysis"
    analysis_root.mkdir()
    retained = analysis_root / "topology.json"
    retained.write_text("{}")
    facts = {"c1": {"win_rate": "0.55", "realised_trade_count": 100}}
    valid = [
        EvidenceRef.model_validate(
            {
                "kind": "canonical_metric",
                "claim_id": "wr",
                "candidate_id": "c1",
                "metric_path": "win_rate",
                "iteration_id": None,
                "analysis_path": None,
            }
        ),
        EvidenceRef.model_validate(
            {
                "kind": "prior_assessment",
                "claim_id": "prior",
                "candidate_id": None,
                "metric_path": None,
                "iteration_id": 2,
                "analysis_path": None,
            }
        ),
        EvidenceRef.model_validate(
            {
                "kind": "analysis_artifact",
                "claim_id": "shape",
                "candidate_id": None,
                "metric_path": None,
                "iteration_id": None,
                "analysis_path": str(retained),
            }
        ),
    ]
    verify_evidence_integrity(
        valid,
        candidate_facts=facts,
        prior_assessment_iterations={2},
        analysis_path=str(retained),
        analysis_root=analysis_root,
    )

    bad_values = [
        EvidenceRef.model_validate(
            {
                "kind": "canonical_metric",
                "claim_id": "fake",
                "candidate_id": "fake",
                "metric_path": "win_rate",
                "iteration_id": None,
                "analysis_path": None,
            }
        ),
        EvidenceRef.model_validate(
            {
                "kind": "canonical_metric",
                "claim_id": "missing-metric",
                "candidate_id": "c1",
                "metric_path": "profit_factor",
                "iteration_id": None,
                "analysis_path": None,
            }
        ),
        EvidenceRef.model_validate(
            {
                "kind": "prior_assessment",
                "claim_id": "missing",
                "candidate_id": None,
                "metric_path": None,
                "iteration_id": 99,
                "analysis_path": None,
            }
        ),
        EvidenceRef.model_validate(
            {
                "kind": "analysis_artifact",
                "claim_id": "arbitrary",
                "candidate_id": None,
                "metric_path": None,
                "iteration_id": None,
                "analysis_path": str(tmp_path / "outside.json"),
            }
        ),
    ]
    for evidence in bad_values:
        with pytest.raises(ValueError):
            verify_evidence_integrity(
                [evidence],
                candidate_facts=facts,
                prior_assessment_iterations={2},
                analysis_path=evidence.analysis_path,
                analysis_root=analysis_root,
            )


def test_v3_init_without_operator_fixture_fails_before_partial_session(tmp_path: Path) -> None:
    repository_template = json.loads(
        (
            Path(__file__).resolve().parents[1] / "autoresearch/templates/ema_anchor_session.json"
        ).read_text()
    )
    repository_template.update(
        contract_version="bbb_autoresearch_state.v3",
        active_stage="A_BASELINE",
        stage_contract={
            "starting_strategy_fixture": "operator-input/missing.json",
            "semantic_bindings": [],
            "measurement_geometries": [{"geometry_id": "A-2", "distance": 2}],
        },
    )
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(repository_template))
    with pytest.raises(ValueError, match="operator starting strategy fixture"):
        initialize_session("v3-missing", template_path, tmp_path)
    assert not (tmp_path / "var/autoresearch/v3-missing").exists()


def test_v3_init_validates_and_freezes_operator_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _strategy()
    fixture_path = tmp_path / "operator.json"
    fixture_path.write_text(json.dumps(fixture))
    template = json.loads(
        (
            Path(__file__).resolve().parents[1] / "autoresearch/templates/ema_anchor_session.json"
        ).read_text()
    )
    template.update(
        contract_version="bbb_autoresearch_state.v3",
        active_stage="A_BASELINE",
        skill_path="skill.md",
        stage_contract={
            "starting_strategy_fixture": str(fixture_path),
            "semantic_bindings": [
                {
                    "dimension": "symmetric_measurement_geometry",
                    "targets": [
                        {
                            "component_role": "exits",
                            "component_id": "atr_stop_loss",
                            "instance_id": "sl",
                            "parameter_name": "distance.multiplier",
                            "fixed_parameters": {},
                        },
                        {
                            "component_role": "exits",
                            "component_id": "atr_take_profit",
                            "instance_id": "tp",
                            "parameter_name": "distance.multiplier",
                            "fixed_parameters": {},
                        },
                    ],
                },
                {
                    "dimension": "anchor_stack_width",
                    "targets": [
                        {
                            "component_role": "setup",
                            "component_id": "anchor_stack_width_setup",
                            "instance_id": "stage-width",
                            "parameter_name": "min_current_width_atr",
                            "fixed_parameters": {"atr_period": 14},
                        }
                    ],
                },
                {
                    "dimension": "untouched_anchor_lookback",
                    "targets": [
                        {
                            "component_role": "setup",
                            "component_id": "untouched_anchor_setup",
                            "instance_id": "stage-lookback",
                            "parameter_name": "lookback",
                            "fixed_parameters": {"active_bars": 3},
                        }
                    ],
                },
            ],
            "measurement_geometries": [{"geometry_id": "A-2", "distance": 2}],
        },
    )
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template))
    (tmp_path / "skill.md").write_text("method")
    catalog = {
        "components": [
            {"component_id": "atr_stop_loss", "params_schema": {}, "params_storage": "nested"},
            {"component_id": "atr_take_profit", "params_schema": {}, "params_storage": "nested"},
            {
                "component_id": "anchor_stack_width_setup",
                "params_storage": "nested",
                "params_schema": {
                    "min_current_width_atr": {"default": 2.0},
                    "atr_period": {"type": "integer", "default": 99},
                },
            },
            {
                "component_id": "untouched_anchor_setup",
                "params_storage": "flat",
                "params_schema": {
                    "lookback": {"type": "integer", "default": 50},
                    "active_bars": {"type": "integer", "default": 99},
                },
            },
        ]
    }

    class Response:
        def __init__(self, value: dict) -> None:
            self.value = value

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.value

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, *_args: object, **_kwargs: object) -> Response:
            return Response(catalog)

        def post(self, *_args: object, **_kwargs: object) -> Response:
            return Response({"ok": True, "errors": []})

    monkeypatch.setattr(autoresearch_init.httpx, "Client", Client)
    monkeypatch.setattr(
        autoresearch_init, "resolve_research_service_base_url", lambda: "http://research"
    )
    monkeypatch.setattr(autoresearch_init, "git_sha", lambda _root: "a" * 40)
    root = initialize_session("v3-valid", template_path, tmp_path)
    state = json.loads((root / "state.json").read_text())
    frozen = copy.deepcopy(state["stage_contract"]["starting_strategy"]["strategy"])
    fixture["ticker"] = "ETHUSDT.P"
    fixture_path.write_text(json.dumps(fixture))
    assert state["contract_version"] == "bbb_autoresearch_state.v3"
    assert state["active_stage"] == "A_BASELINE"
    assert state["stage_contract"]["starting_strategy"]["strategy"] == frozen
    bindings = {item["dimension"]: item for item in state["stage_contract"]["semantic_bindings"]}
    assert bindings["anchor_stack_width"]["targets"][0]["fixed_parameters"] == {"atr_period": 14}
    assert bindings["untouched_anchor_lookback"]["targets"][0]["fixed_parameters"] == {
        "active_bars": 3
    }

    original_fixture = _strategy()
    cases = []
    wrong_template = copy.deepcopy(template)
    wrong_template["stage_contract"]["semantic_bindings"][0]["targets"][0]["instance_id"] = "wrong"
    cases.append(("v3-wrong-exit", wrong_template, copy.deepcopy(original_fixture)))

    missing_fixture = copy.deepcopy(original_fixture)
    missing_fixture["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"].pop()
    cases.append(("v3-missing-exit", copy.deepcopy(template), missing_fixture))

    ambiguous_fixture = copy.deepcopy(original_fixture)
    exits = ambiguous_fixture["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"]
    exits.append(copy.deepcopy(exits[0]))
    cases.append(("v3-ambiguous-exit", copy.deepcopy(template), ambiguous_fixture))

    for session_id, bad_template, bad_fixture in cases:
        bad_fixture_path = tmp_path / f"{session_id}.json"
        bad_fixture_path.write_text(json.dumps(bad_fixture))
        bad_template["stage_contract"]["starting_strategy_fixture"] = str(bad_fixture_path)
        bad_template_path = tmp_path / f"{session_id}-template.json"
        bad_template_path.write_text(json.dumps(bad_template))
        with pytest.raises(ValueError, match="missing or ambiguous"):
            initialize_session(session_id, bad_template_path, tmp_path)
        assert not (tmp_path / "var/autoresearch" / session_id).exists()


def test_v3_prompts_receive_compact_exact_stage_controls(tmp_path: Path) -> None:
    state = _state()
    state.update(
        contract_version="bbb_autoresearch_state.v3",
        session_id="prompt-v3",
        iteration=0,
        skill_path=".claude/skills/ema-anchor-edge-research/SKILL.md",
    )
    iteration = tmp_path / "iteration"
    repository = Path(__file__).resolve().parents[1]
    planning = render_planning_prompt(state, repository, iteration, "http://research")
    interpretation = render_interpretation_prompt(state, repository, iteration, "batch")
    for prompt in (planning, interpretation):
        assert '"active_stage": "A_BASELINE"' in prompt
        assert '"symmetric_measurement_geometry"' in prompt
        assert '"geometry_id": "A-2"' in prompt
    assert "does not optimize exits" in planning
    assert "B3 is optional" in planning


def test_geometry_references_published_for_every_sanctioned_a_baseline_geometry() -> None:
    # Harness contract fix: the planning worker must be able to read its
    # A_BASELINE geometry's canonical reference hash straight from state,
    # never compute it, so state.stage_contract must publish one entry per
    # configured geometry (A-2/A-3/A-4 for the approved template).
    contract = _contract()
    published = {item["geometry_id"]: item["resolved_sha256"] for item in contract["geometry_references"]}
    assert set(published) == {"A-2", "A-3", "A-4"}
    for geometry_id, resolved_sha256 in published.items():
        assert resolved_sha256 == canonical_sha256(
            reference_strategy({"stage_contract": contract}, geometry_id)
        )


def test_geometry_references_matches_canonical_reference_strategy_computation() -> None:
    # No second independent implementation: geometry_references() must be
    # produced by the exact same reference_strategy()/canonical_sha256()
    # pair the supervisor re-runs during validate_stage_request().
    contract = _contract()
    for geometry_id in ("A-2", "A-3", "A-4"):
        expected = canonical_sha256(reference_strategy({"stage_contract": contract}, geometry_id))
        published = next(
            item["resolved_sha256"]
            for item in contract["geometry_references"]
            if item["geometry_id"] == geometry_id
        )
        assert published == expected


def test_planner_can_build_candidate_using_only_published_state_metadata() -> None:
    # The worker never needs to execute reference_strategy()/canonical_sha256()
    # itself: state.stage_contract.geometry_references already carries the
    # exact hash it must echo into stage_context.reference_strategy_sha256,
    # and a canonical candidate built from public state alone is accepted.
    state = _state()
    geometry_id = "A-3"
    published_hash = next(
        item["resolved_sha256"]
        for item in state["stage_contract"]["geometry_references"]
        if item["geometry_id"] == geometry_id
    )
    plan = _plan(state, geometry_id)
    assert plan["stage_context"]["reference_strategy_sha256"] == published_hash
    strategy = reference_strategy(state, geometry_id)
    validate_stage_request(_request(strategy), plan, state)


def test_forged_geometry_reference_hash_is_rejected_by_stage_contract_validation() -> None:
    # Publishing the expected hash never replaces independent supervisor
    # verification: a tampered geometry_references entry fails closed at
    # freeze time.
    contract = _contract()
    contract["geometry_references"][0]["resolved_sha256"] = "0" * 64
    with pytest.raises(StageContractError, match="inconsistent"):
        validate_stage_contract(contract)


def test_forged_candidate_hash_is_rejected_despite_correct_published_reference() -> None:
    # A candidate that doesn't actually match the published/canonical
    # reference is still rejected at request-validation time, independent of
    # what geometry_references claims.
    state = _state()
    strategy = reference_strategy(state, "A-2")
    tampered = copy.deepcopy(strategy)
    tampered["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"][0]["distance"][
        "multiplier"
    ] = 999
    plan = _plan(state, "A-2")
    with pytest.raises(StageContractError, match="differs from configured/reference geometry"):
        validate_stage_request(_request(tampered), plan, state)
