#!/usr/bin/env python3
"""Initialize one durable BBB AutoResearch session."""

from __future__ import annotations

import argparse
import json
import sys
import hashlib
from pathlib import Path
from typing import Any

import httpx

from autoresearch_supervisor import (
    REPO_ROOT,
    STATE_VERSION,
    STATE_VERSION_V2,
    atomic_write_json,
    git_sha,
    session_dir,
    utc_now,
    validate_state,
    resolve_research_service_base_url,
)
from autoresearch_quality_contracts import phase_binding, validate_policy
from autoresearch_stage_contracts import (
    STATE_VERSION_V3,
    canonical_sha256,
    geometry_references,
    validate_resolved_stage_targets,
    validate_stage_contract,
)


def _validate_explicit_catalog_value(name: str, value: Any, definition: dict[str, Any]) -> None:
    kind = definition.get("type")
    if (
        (kind == "integer" and (type(value) is not int))
        or (kind == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)))
        or (kind == "string" and not isinstance(value, str))
    ):
        raise ValueError(f"explicit fixed parameter {name} has wrong catalog type")
    if definition.get("enum") is not None and value not in definition["enum"]:
        raise ValueError(f"explicit fixed parameter {name} is outside catalog enum")
    if definition.get("min") is not None and value < definition["min"]:
        raise ValueError(f"explicit fixed parameter {name} is below catalog minimum")
    if definition.get("max") is not None and value > definition["max"]:
        raise ValueError(f"explicit fixed parameter {name} is above catalog maximum")


def _load_v3_stage_contract(
    template: dict[str, Any], template_path: Path, repo_root: Path
) -> dict[str, Any]:
    config = template.get("stage_contract")
    if not isinstance(config, dict):
        raise ValueError("v3 template requires stage_contract")
    fixture_name = config.get("starting_strategy_fixture")
    if not isinstance(fixture_name, str) or not fixture_name:
        raise ValueError("v3 template requires an operator-approved starting_strategy_fixture")
    fixture_path = Path(fixture_name)
    if not fixture_path.is_absolute():
        fixture_path = repo_root / fixture_path
    try:
        source = fixture_path.read_bytes()
        fixture = json.loads(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load operator starting strategy fixture: {exc}") from exc
    stack = fixture.get("raw_spec", {}).get("anchor_stack", {})
    periods = tuple(stack.get(role, {}).get("period") for role in ("fast", "anchor", "slow"))
    if periods != (100, 200, 500):
        raise ValueError(
            "controlled EMA A-to-B starting strategy must use fast/anchor/slow EMA100/200/500"
        )
    try:
        base_url = resolve_research_service_base_url()
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            catalog_response = client.get(
                "/api/research/component-catalog", params={"strategy_id": fixture["strategy_id"]}
            )
            catalog_response.raise_for_status()
            catalog = catalog_response.json()
            validation_response = client.post(
                "/api/research/config/validate",
                json={
                    "config_version": 1,
                    "experiment_id": f"autoresearch-init-{template_path.stem}",
                    "strategy_id": fixture["strategy_id"],
                    "execution": {},
                    "instances": [fixture],
                },
            )
            validation_response.raise_for_status()
            validation = validation_response.json()
    except (httpx.HTTPError, KeyError, TypeError) as exc:
        raise ValueError(f"canonical starting-strategy validation unavailable: {exc}") from exc
    if validation.get("ok") is not True:
        raise ValueError(f"canonical starting strategy is invalid: {validation.get('errors')}")
    components = {item.get("component_id"): item for item in catalog.get("components", [])}
    bindings = config.get("semantic_bindings")
    if not isinstance(bindings, list):
        raise ValueError("v3 template semantic_bindings must be an array")
    for binding in bindings:
        targets = binding.get("targets")
        if not isinstance(targets, list):
            raise ValueError("semantic binding targets must be an array")
        for target in targets:
            component_id = target.get("component_id")
            component = components.get(component_id)
            if component is None:
                raise ValueError(
                    f"semantic binding component absent from live catalog: {component_id}"
                )
            allowed = set(component.get("params_schema", {}))
            parameter = target.get("parameter_name")
            fixed = target.get("fixed_parameters")
            if not isinstance(fixed, dict):
                raise ValueError("semantic target requires explicit fixed_parameters")
            if binding.get("dimension") == "symmetric_measurement_geometry":
                if parameter != "distance.multiplier":
                    raise ValueError("geometry target must use distance.multiplier")
                if fixed:
                    raise ValueError("geometry target fixed_parameters must be empty")
                target["params_storage"] = "structural"
            else:
                if parameter not in allowed:
                    raise ValueError(
                        f"semantic binding parameter absent from live catalog: {component_id}.{parameter}"
                    )
                required_fixed = allowed - {parameter}
                if set(fixed) != required_fixed:
                    raise ValueError(
                        f"semantic target fixed_parameters differ from catalog schema: "
                        f"missing={sorted(required_fixed - set(fixed))}, "
                        f"extra={sorted(set(fixed) - required_fixed)}"
                    )
                for name, value in fixed.items():
                    _validate_explicit_catalog_value(name, value, component["params_schema"][name])
                target["params_storage"] = component.get("params_storage")
    normalized = fixture
    contract = {
        "contract_version": "bbb_autoresearch_stage_contract.v2",
        "programme": "EMA_ANCHOR_A_TO_B",
        "starting_strategy": {
            "source_path": str(fixture_path.resolve()),
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "resolved_sha256": canonical_sha256(normalized),
            "strategy": normalized,
        },
        "semantic_bindings": bindings,
        "measurement_geometries": config.get("measurement_geometries"),
    }
    contract["geometry_references"] = geometry_references(contract)
    validate_stage_contract(contract)
    validate_resolved_stage_targets(contract)
    return contract


def initialize_session(session_id: str, template_path: Path, repo_root: Path = REPO_ROOT) -> Path:
    root = session_dir(session_id, repo_root)
    if root.exists():
        raise FileExistsError(f"session already exists: {root}")
    try:
        template: dict[str, Any] = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid session template: {exc}") from exc
    now = utc_now()
    policy_value = template.get("research_quality_policy")
    policy = validate_policy(policy_value) if policy_value is not None else None
    wants_v3 = template.get("contract_version") == STATE_VERSION_V3
    if wants_v3 and policy is None:
        raise ValueError("v3 session requires research_quality_policy")
    stage_contract = (
        _load_v3_stage_contract(template, template_path, repo_root) if wants_v3 else None
    )
    state_version = (
        STATE_VERSION_V3
        if wants_v3
        else (STATE_VERSION_V2 if policy is not None else STATE_VERSION)
    )
    phase = template.get("phase", "baseline")
    state: dict[str, Any] = {
        "contract_version": state_version,
        "session_id": session_id,
        "research_program": template["research_program"],
        "skill_path": template["skill_path"],
        "strategy_context": template.get("strategy_context", {}),
        "status": "initialized",
        "baseline_git_sha": git_sha(repo_root),
        "created_at": now,
        "updated_at": now,
        "iteration": 0,
        "phase": phase,
        "completed_phases": template.get("completed_phases", []),
        "current_hypothesis": template.get("current_hypothesis"),
        "competing_explanations": template.get("competing_explanations", []),
        "findings": template.get("findings", []),
        "structural_dimensions_known": template.get("structural_dimensions_known", []),
        "tested_ranges": template.get("tested_ranges", []),
        "observed_response_shapes": template.get("observed_response_shapes", []),
        "promising_regions": template.get("promising_regions", []),
        "rejected_regions": template.get("rejected_regions", []),
        "aggregate_interpretation": template.get("aggregate_interpretation"),
        "long_interpretation": template.get("long_interpretation"),
        "short_interpretation": template.get("short_interpretation"),
        "side_asymmetry": template.get("side_asymmetry"),
        "thinning_risk": template.get("thinning_risk"),
        "temporal_regime_concentration_concern": template.get(
            "temporal_regime_concentration_concern"
        ),
        "other_confounders": template.get("other_confounders", []),
        "unresolved_questions": template.get("unresolved_questions", []),
        "validation_status": template.get("validation_status"),
        "next_discriminating_question": template.get("next_discriminating_question"),
        "next_experiment": template.get("next_experiment"),
        "last_iteration_result": None,
        "budgets": {
            "max_iterations": template.get("budgets", {}).get("max_iterations"),
            "max_wall_clock_seconds": template.get("budgets", {}).get("max_wall_clock_seconds"),
            "max_consecutive_agent_failures": template.get("budgets", {}).get(
                "max_consecutive_agent_failures", 3
            ),
            "max_candidates_per_iteration": template.get("budgets", {}).get(
                "max_candidates_per_iteration"
            ),
        },
        "stop_reason": None,
    }
    if policy is not None:
        state.update(
            research_quality_policy=policy.model_dump(mode="json"),
            active_stage_binding=phase_binding(policy, phase).model_dump(mode="json"),
            latest_quality_assessment=None,
            promotion_history=[],
        )
    if stage_contract is not None:
        active_stage = template.get("active_stage", "A_CONTROL")
        if active_stage != "A_CONTROL":
            raise ValueError("a new v3 session must start at A_CONTROL")
        state.update(
            stage_contract=stage_contract,
            active_stage=active_stage,
            phase_a_references=[],
            stage_dispositions=[],
            stage_history=[],
        )
    validate_state(state)
    skill = repo_root / state["skill_path"]
    if not skill.is_file():
        raise ValueError(f"domain skill does not exist: {skill}")
    root.mkdir(parents=True, exist_ok=False)
    (root / "iterations").mkdir()
    atomic_write_json(root / "state.json", state)
    (root / "journal.jsonl").touch(exist_ok=False)
    atomic_write_json(
        root / "bootstrap.json",
        {
            "contract_version": "bbb_autoresearch_bootstrap.v1",
            "execution_protocol": "bbb_autoresearch_supervisor_execution.v1",
            "session_id": session_id,
            "baseline_git_sha": state["baseline_git_sha"],
            "template_path": str(template_path.resolve()),
            "created_at": now,
            **(
                {
                    "starting_strategy_source_sha256": stage_contract["starting_strategy"][
                        "source_sha256"
                    ],
                    "starting_strategy_resolved_sha256": stage_contract["starting_strategy"][
                        "resolved_sha256"
                    ],
                }
                if stage_contract is not None
                else {}
            ),
        },
    )
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args(argv)
    root = initialize_session(args.session, args.template)
    print(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
