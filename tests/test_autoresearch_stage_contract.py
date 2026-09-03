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
    expected_prerequisite_disposition_refs,
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
                                "distance": {"period": 14, "timeframe": "base", "multiplier": 3},
                            },
                            {
                                "component_id": "atr_take_profit",
                                "instance_id": "tp",
                                "exit_kind": "take_profit",
                                "distance": {"period": 14, "timeframe": "base", "multiplier": 3},
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
    return {
        "contract_version": "bbb_autoresearch_stage_contract.v2",
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
    }


_STAGE_ORDER = (
    "A_CONTROL",
    "B1_WIDTH",
    "B2_LOOKBACK",
    "B3_WIDTH_X_LOOKBACK",
    "C_ENTRY_REGION_SELECTION",
    "D_EXIT_GEOMETRY",
)
_STAGE_KINDS = {
    "A_CONTROL": "descriptive_baseline",
    "B1_WIDTH": "structural_entry",
    "B2_LOOKBACK": "structural_entry",
    "B3_WIDTH_X_LOOKBACK": "structural_interaction",
    "C_ENTRY_REGION_SELECTION": "entry_region_selection",
    "D_EXIT_GEOMETRY": "exit_geometry",
}


def _state(stage: str = "A_CONTROL") -> dict:
    refs = [] if stage == "A_CONTROL" else [{"experiment_id": "control-reference"}]
    prior_stages = _STAGE_ORDER[: _STAGE_ORDER.index(stage)]
    dispositions = [
        {
            "iteration_id": index,
            "disposition": {
                "stage": prior_stage,
                "status": "characterized",
                "evidence": [_evidence(index)],
            },
        }
        for index, prior_stage in enumerate(prior_stages, start=1)
    ]
    return {
        "active_stage": stage,
        "active_stage_binding": {"phase": STAGE_PHASES[stage], "stage_kind": _STAGE_KINDS[stage]},
        "stage_contract": _contract(),
        "phase_a_references": refs,
        "stage_dispositions": dispositions,
    }


_REQUIRED_STAGES = {
    "A_CONTROL": set(),
    "B1_WIDTH": {"A_CONTROL"},
    "B2_LOOKBACK": {"A_CONTROL"},
    "B3_WIDTH_X_LOOKBACK": {"A_CONTROL", "B1_WIDTH", "B2_LOOKBACK"},
    "C_ENTRY_REGION_SELECTION": set(),
    "D_EXIT_GEOMETRY": set(),
}


def _plan(state: dict) -> dict:
    required_stage_names = _REQUIRED_STAGES[state["active_stage"]]
    required = [
        entry["iteration_id"]
        for entry in state["stage_dispositions"]
        if entry["disposition"]["status"] != "in_progress"
        and entry["disposition"]["stage"] in required_stage_names
    ]
    dimensions = {
        "A_CONTROL": [],
        "B1_WIDTH": ["anchor_stack_width"],
        "B2_LOOKBACK": ["untouched_anchor_lookback"],
        "B3_WIDTH_X_LOOKBACK": ["anchor_stack_width", "untouched_anchor_lookback"],
        "C_ENTRY_REGION_SELECTION": [],
        "D_EXIT_GEOMETRY": [],
    }[state["active_stage"]]
    return {
        "stage_context": {
            "active_stage": state["active_stage"],
            "starting_strategy_sha256": state["stage_contract"]["starting_strategy"][
                "resolved_sha256"
            ],
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


def test_stage_contract_rejects_unknown_dimension() -> None:
    contract = _contract()
    validate_stage_contract(contract)
    contract["semantic_bindings"][0]["dimension"] = "json_path"
    with pytest.raises(StageContractError):
        validate_stage_contract(contract)


def test_phase_a_control_accepts_exactly_one_frozen_candidate() -> None:
    state = _state()
    strategy = reference_strategy(state)
    validate_stage_request(_request(strategy), _plan(state), state)
    asymmetric = copy.deepcopy(strategy)
    asymmetric["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"][0]["distance"][
        "multiplier"
    ] = 9
    with pytest.raises(StageContractError, match="outside"):
        validate_stage_request(_request(asymmetric), _plan(state), state)
    with pytest.raises(StageContractError, match="exactly one"):
        validate_stage_request(_request(strategy, strategy), _plan(state), state)


def test_phase_a_control_rejects_a_second_measurement() -> None:
    state = _state()
    state["phase_a_references"] = [{"experiment_id": "already-measured"}]
    strategy = reference_strategy(state)
    with pytest.raises(StageContractError, match="already has an accepted reference"):
        validate_stage_request(_request(strategy), _plan(state), state)


def test_b1_allows_only_width_and_preserves_frozen_control_exit() -> None:
    state = _state("B1_WIDTH")
    candidate = reference_strategy(state)
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

    exit_mutation = reference_strategy(state)
    exit_mutation["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"][0][
        "distance"
    ]["multiplier"] = 9
    with pytest.raises(StageContractError, match="outside"):
        validate_stage_request(_request(exit_mutation), _plan(state), state)

    fixed_mutation = reference_strategy(state)
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
    candidate = reference_strategy(state)
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
    # _state("B2_LOOKBACK") already durably closes A_CONTROL (iteration 1)
    # and B1_WIDTH (iteration 2) as prerequisites.
    state = _state("B2_LOOKBACK")
    candidate = reference_strategy(state)
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


def test_b_stage_requires_a_completed_control_reference() -> None:
    state = _state("B1_WIDTH")
    state["phase_a_references"] = []
    candidate = reference_strategy(state)
    with pytest.raises(StageContractError, match="requires a completed Phase-A control reference"):
        validate_stage_request(_request(candidate), _plan(state), state)


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
        active_stage="A_CONTROL",
        stage_contract={
            "starting_strategy_fixture": "operator-input/missing.json",
            "semantic_bindings": [],
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
        active_stage="A_CONTROL",
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
    assert state["active_stage"] == "A_CONTROL"
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
        assert '"active_stage": "A_CONTROL"' in prompt
        assert '"symmetric_measurement_geometry"' in prompt
    assert "not scan or optimize exit geometry" in planning
    assert "B3 is optional" in planning
    assert "broad coarse sweep" in planning
    assert "map the response topology" in planning
    assert "not to select the best sampled point" in planning
    assert "all supported or plausibly distinct neighborhoods" in " ".join(planning.split())
    assert "unresolved boundaries remain" in planning
    assert "Active stage: A_CONTROL" in planning
    assert "Mutable semantic dimensions for this stage (the only fields you may vary): (none)" in (
        planning
    )
    assert "Exact prerequisite_disposition_refs your stage_context MUST declare: []" in planning


def test_planning_prompt_states_b1_and_b2_independent_baseline_authority(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    for stage, expected_mutable in (("B1_WIDTH", "anchor_stack_width"), ("B2_LOOKBACK", "untouched_anchor_lookback")):
        state = _state(stage)
        state.update(
            contract_version="bbb_autoresearch_state.v3",
            session_id="prompt-v3",
            iteration=1,
            skill_path=".claude/skills/ema-anchor-edge-research/SKILL.md",
        )
        planning = render_planning_prompt(state, repository, tmp_path / stage, "http://research")
        assert f"Active stage: {stage}" in planning
        assert f"you may vary): ['{expected_mutable}']" in planning
        assert "independent baselines off the frozen A_CONTROL strategy" in planning
        assert "B1 does not inherit any lookback choice from B2" in planning
        expected_refs = expected_prerequisite_disposition_refs(stage, state)
        assert (
            f"Exact prerequisite_disposition_refs your stage_context MUST declare: {expected_refs}"
            in planning
        )


def test_planning_prompt_states_b3_evidence_guided_joint_search_authority(tmp_path: Path) -> None:
    state = _state("B3_WIDTH_X_LOOKBACK")
    state.update(
        contract_version="bbb_autoresearch_state.v3",
        session_id="prompt-v3",
        iteration=1,
        skill_path=".claude/skills/ema-anchor-edge-research/SKILL.md",
    )
    repository = Path(__file__).resolve().parents[1]
    planning = render_planning_prompt(state, repository, tmp_path, "http://research")
    assert "Active stage: B3_WIDTH_X_LOOKBACK" in planning
    assert (
        "you may vary): ['anchor_stack_width', 'untouched_anchor_lookback']" in planning
    )
    assert "Choose the joint search region from the durable evidence" in planning
    assert "do not simply carry forward one 'winner point'" in planning
    assert "how the proposed width/lookback ranges follow from the B1 and B2 evidence" in planning
    expected_refs = expected_prerequisite_disposition_refs("B3_WIDTH_X_LOOKBACK", state)
    assert expected_refs == [1, 2, 3]
    assert (
        f"Exact prerequisite_disposition_refs your stage_context MUST declare: {expected_refs}"
        in planning
    )


def test_forged_candidate_is_rejected_despite_matching_starting_strategy_hash() -> None:
    # A candidate that doesn't actually match the frozen control strategy is
    # still rejected at request-validation time.
    state = _state()
    strategy = reference_strategy(state)
    tampered = copy.deepcopy(strategy)
    tampered["raw_spec"]["trade_management"]["exit_policy"]["always_on"]["exits"][0]["distance"][
        "multiplier"
    ] = 999
    plan = _plan(state)
    with pytest.raises(StageContractError, match="outside active semantic dimensions"):
        validate_stage_request(_request(tampered), plan, state)


def test_c_and_d_are_unreachable_provisional_stages() -> None:
    # C_ENTRY_REGION_SELECTION and D_EXIT_GEOMETRY exist as reserved stage
    # names/phase bindings only. Their behavioral contract (state shape,
    # shortlist acceptance rule, per-region reference identity) is
    # deliberately undefined until real B1/B2/B3 evidence from a HOST
    # research run shows what shape it takes -- no plan may target either
    # stage yet, even once every prior stage is durably closed.
    for stage in ("C_ENTRY_REGION_SELECTION", "D_EXIT_GEOMETRY"):
        state = _state(stage)
        plan = _plan(state)
        with pytest.raises(StageContractError, match="not yet defined"):
            validate_stage_context(plan["stage_context"], state)


def test_b2_lookback_does_not_require_b1_width_closed() -> None:
    # B1_WIDTH and B2_LOOKBACK are independent branches off A_CONTROL, not
    # prerequisites of each other.
    state = _state("A_CONTROL")
    state["active_stage"] = "B2_LOOKBACK"
    state["active_stage_binding"] = {"phase": "structural_1d", "stage_kind": "structural_entry"}
    state["phase_a_references"] = [{"experiment_id": "control-reference"}]
    state["stage_dispositions"] = [
        {
            "iteration_id": 1,
            "disposition": {
                "stage": "A_CONTROL",
                "status": "characterized",
                "evidence": [_evidence(1)],
            },
        }
    ]
    plan = _plan(state)
    assert plan["stage_context"]["prerequisite_disposition_refs"] == [1]
    validate_stage_context(plan["stage_context"], state)
    candidate = reference_strategy(state)
    candidate["raw_spec"]["setups"].append(
        {
            "component_id": "untouched_anchor_setup",
            "instance_id": "stage-lookback",
            "lookback": 50,
            "active_bars": 3,
        }
    )
    validate_stage_request(_request(candidate), plan, state)
