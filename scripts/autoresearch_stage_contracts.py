"""Typed, programme-specific A→B stage contracts for BBB AutoResearch v3."""

from __future__ import annotations

import copy
import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from research_service.application.experiments import BatchExperimentRequest
from research_service.domain.strategy_instance import DeployableStrategyInstance
from autoresearch_quality_contracts import EvidenceRef

STAGE_CONTRACT_VERSION = "bbb_autoresearch_stage_contract.v1"
STATE_VERSION_V3 = "bbb_autoresearch_state.v3"
PLAN_VERSION_V2 = "bbb_autoresearch_execution_plan.v2"
ITERATION_VERSION_V3 = "bbb_autoresearch_iteration.v3"
JOURNAL_VERSION_V3 = "bbb_autoresearch_journal.v3"

STAGES = ("A_BASELINE", "B1_WIDTH", "B2_LOOKBACK", "B3_WIDTH_X_LOOKBACK")
DIMENSIONS = (
    "symmetric_measurement_geometry",
    "anchor_stack_width",
    "untouched_anchor_lookback",
)
STAGE_DIMENSIONS = {
    "A_BASELINE": ("symmetric_measurement_geometry",),
    "B1_WIDTH": ("anchor_stack_width",),
    "B2_LOOKBACK": ("untouched_anchor_lookback",),
    "B3_WIDTH_X_LOOKBACK": ("anchor_stack_width", "untouched_anchor_lookback"),
}
STAGE_PHASES = {
    "A_BASELINE": "baseline",
    "B1_WIDTH": "structural_1d",
    "B2_LOOKBACK": "structural_1d",
    "B3_WIDTH_X_LOOKBACK": "structural_interaction",
}
DISPOSITIONS = ("in_progress", "characterized", "terminally_rejected")


class StageContractError(ValueError):
    pass


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _exact(value: dict[str, Any], keys: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise StageContractError(
            f"{context} fields differ: missing={sorted(keys - actual)}, extra={sorted(actual - keys)}"
        )


def _hash(value: object, context: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise StageContractError(f"{context} must be a lowercase SHA256")


def validate_stage_contract(value: dict[str, Any]) -> dict[str, Any]:
    _exact(
        value,
        {
            "contract_version",
            "programme",
            "starting_strategy",
            "semantic_bindings",
            "measurement_geometries",
            "geometry_references",
        },
        "stage contract",
    )
    if (
        value["contract_version"] != STAGE_CONTRACT_VERSION
        or value["programme"] != "EMA_ANCHOR_A_TO_B"
    ):
        raise StageContractError("stage contract identity is invalid")
    start = value["starting_strategy"]
    _exact(
        start, {"source_path", "source_sha256", "resolved_sha256", "strategy"}, "starting strategy"
    )
    if not isinstance(start["source_path"], str) or not start["source_path"]:
        raise StageContractError("starting strategy source_path is invalid")
    _hash(start["source_sha256"], "starting strategy source_sha256")
    _hash(start["resolved_sha256"], "starting strategy resolved_sha256")
    try:
        strategy = DeployableStrategyInstance.model_validate(start["strategy"])
    except ValidationError as exc:
        raise StageContractError(f"starting strategy is invalid: {exc}") from exc
    normalized = strategy.model_dump(mode="json")
    if canonical_sha256(normalized) != start["resolved_sha256"]:
        raise StageContractError("starting strategy resolved_sha256 is inconsistent")
    bindings = value["semantic_bindings"]
    if not isinstance(bindings, list) or {
        item.get("dimension") for item in bindings if isinstance(item, dict)
    } != set(DIMENSIONS):
        raise StageContractError("semantic bindings must contain each typed dimension exactly once")
    for item in bindings:
        _exact(item, {"dimension", "targets"}, "semantic binding")
        if item["dimension"] not in DIMENSIONS:
            raise StageContractError("unknown semantic dimension")
        targets = item["targets"]
        expected_target_count = 2 if item["dimension"] == "symmetric_measurement_geometry" else 1
        if not isinstance(targets, list) or len(targets) != expected_target_count:
            raise StageContractError("semantic binding target count is invalid")
        identities: list[tuple[str, str | None]] = []
        for target in targets:
            _exact(
                target,
                {
                    "component_role",
                    "component_id",
                    "instance_id",
                    "parameter_name",
                    "params_storage",
                    "fixed_parameters",
                },
                "semantic target",
            )
            if not all(
                isinstance(target[k], str) and target[k]
                for k in ("component_role", "component_id", "parameter_name")
            ):
                raise StageContractError("semantic target role/component/parameter is invalid")
            if target["instance_id"] is not None and (
                not isinstance(target["instance_id"], str) or not target["instance_id"]
            ):
                raise StageContractError("semantic target instance_id is invalid")
            if (
                target["params_storage"] not in {"flat", "nested", "structural"}
                or not isinstance(target["fixed_parameters"], dict)
                or target["parameter_name"] in target["fixed_parameters"]
            ):
                raise StageContractError("semantic target parameter contract is invalid")
            identities.append((target["component_id"], target["instance_id"]))
        if len(identities) != len(set(identities)):
            raise StageContractError("semantic target identities must be unique")
    geometries = value["measurement_geometries"]
    if not isinstance(geometries, list) or not geometries:
        raise StageContractError("measurement_geometries must be non-empty")
    ids: list[str] = []
    for geometry in geometries:
        _exact(geometry, {"geometry_id", "distance"}, "measurement geometry")
        if not isinstance(geometry["geometry_id"], str) or not geometry["geometry_id"]:
            raise StageContractError("geometry_id is invalid")
        try:
            if Decimal(str(geometry["distance"])) <= 0:
                raise StageContractError("geometry distance must be positive")
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise StageContractError("geometry distance must be numeric") from exc
        ids.append(geometry["geometry_id"])
    if len(ids) != len(set(ids)):
        raise StageContractError("measurement geometry IDs must be unique")
    # Published sanctioned per-geometry reference hashes are never trusted
    # as-is: the supervisor independently recomputes them here from the same
    # `reference_strategy()`/`canonical_sha256()` source of truth used to
    # publish them, so a forged or stale published value is fail-closed
    # rejected rather than silently trusted.
    published = value["geometry_references"]
    if not isinstance(published, list) or [
        item.get("geometry_id") if isinstance(item, dict) else None for item in published
    ] != ids:
        raise StageContractError(
            "geometry_references must list exactly the configured measurement geometries, "
            "in order"
        )
    expected_references = geometry_references(value)
    for item, expected in zip(published, expected_references, strict=True):
        _exact(item, {"geometry_id", "resolved_sha256"}, "geometry reference")
        _hash(item["resolved_sha256"], "geometry reference resolved_sha256")
        if item != expected:
            raise StageContractError(
                "published geometry_references is inconsistent with the canonical "
                "reference_strategy computation"
            )
    return value


def validate_stage_context(value: dict[str, Any], state: dict[str, Any]) -> None:
    _exact(
        value,
        {
            "active_stage",
            "starting_strategy_sha256",
            "geometry_id",
            "reference_strategy_sha256",
            "allowed_semantic_dimensions",
            "prerequisite_disposition_refs",
        },
        "stage context",
    )
    stage = value["active_stage"]
    if stage != state["active_stage"]:
        raise StageContractError("plan stage differs from state")
    expected_dims = list(STAGE_DIMENSIONS[stage])
    if value["allowed_semantic_dimensions"] != expected_dims:
        raise StageContractError("allowed semantic dimensions differ from stage authority")
    expected_hash = state["stage_contract"]["starting_strategy"]["resolved_sha256"]
    if value["starting_strategy_sha256"] != expected_hash:
        raise StageContractError("starting strategy hash differs from state")
    _hash(value["reference_strategy_sha256"], "reference strategy hash")
    if not isinstance(value["prerequisite_disposition_refs"], list) or any(
        type(x) is not int or x < 1 for x in value["prerequisite_disposition_refs"]
    ):
        raise StageContractError("prerequisite disposition refs are invalid")
    if len(value["prerequisite_disposition_refs"]) != len(
        set(value["prerequisite_disposition_refs"])
    ):
        raise StageContractError("prerequisite disposition refs must be unique")
    required_stages = {
        "A_BASELINE": set(),
        "B1_WIDTH": {"A_BASELINE"},
        "B2_LOOKBACK": {"A_BASELINE", "B1_WIDTH"},
        "B3_WIDTH_X_LOOKBACK": {"A_BASELINE", "B1_WIDTH", "B2_LOOKBACK"},
    }[stage]
    accepted = {
        entry["iteration_id"]: entry["disposition"]["stage"]
        for entry in state["stage_dispositions"]
        if entry["disposition"]["status"] in {"characterized", "terminally_rejected"}
    }
    refs = value["prerequisite_disposition_refs"]
    if set(refs) != {
        iteration for iteration, prior_stage in accepted.items() if prior_stage in required_stages
    }:
        raise StageContractError(
            "prerequisite disposition refs differ from durable causal prerequisites"
        )
    geometry_id = value["geometry_id"]
    if not isinstance(geometry_id, str) or not geometry_id:
        raise StageContractError("stage context geometry_id is invalid")
    if (
        canonical_sha256(reference_strategy(state, geometry_id))
        != value["reference_strategy_sha256"]
    ):
        raise StageContractError("reference strategy hash is inconsistent")


def _binding(contract: dict[str, Any], dimension: str) -> dict[str, Any]:
    return next(item for item in contract["semantic_bindings"] if item["dimension"] == dimension)


def _all_exits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    policy = raw.get("trade_management", {}).get("exit_policy", {})
    groups = [policy.get("always_on", {})] + [
        policy.get("profiles", {}).get(name, {}) for name in ("aligned", "countertrend", "neutral")
    ]
    return [item for group in groups for item in group.get("exits", [])]


def _instances(raw: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    role = target["component_role"]
    if role == "exits":
        candidates = _all_exits(raw)
    elif role == "setup":
        candidates = raw.get("setups", [])
    else:
        raise StageContractError(f"unsupported bound component role {role}")
    return candidates


def _find_instance(raw: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    matches = [
        x
        for x in _instances(raw, target)
        if x.get("component_id") == target["component_id"]
        and (target["instance_id"] is None or x.get("instance_id") == target["instance_id"])
    ]
    if len(matches) != 1:
        raise StageContractError("bound semantic target is missing or ambiguous")
    return matches[0]


def validate_resolved_stage_targets(contract: dict[str, Any]) -> None:
    """Resolve mandatory starting-strategy targets before session creation."""

    validate_stage_contract(contract)
    raw = contract["starting_strategy"]["strategy"]["raw_spec"]
    geometry = _binding(contract, "symmetric_measurement_geometry")
    exit_kinds: set[str] = set()
    for target in geometry["targets"]:
        if (
            target["component_role"] != "exits"
            or target["parameter_name"] != "distance.multiplier"
            or target["params_storage"] != "structural"
        ):
            raise StageContractError("geometry target contract is invalid")
        instance = _find_instance(raw, target)
        distance = instance.get("distance")
        if not isinstance(distance, dict) or "multiplier" not in distance:
            raise StageContractError("bound exit has no distance.multiplier")
        exit_kinds.add(str(instance.get("exit_kind")))
    if exit_kinds != {"stop_loss", "take_profit"}:
        raise StageContractError("geometry targets must resolve one stop-loss and one take-profit")

    # B1/B2 targets are explicit prototypes that may be absent from the naked
    # strategy.  If an identity is already present, it must still be unique;
    # otherwise enabling the typed dimension later would be ambiguous.
    for dimension in ("anchor_stack_width", "untouched_anchor_lookback"):
        target = _binding(contract, dimension)["targets"][0]
        matches = [
            item
            for item in _instances(raw, target)
            if item.get("component_id") == target["component_id"]
            and item.get("instance_id") == target["instance_id"]
        ]
        if len(matches) > 1:
            raise StageContractError(f"{dimension} prototype identity is ambiguous")


def geometry_references(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Sanctioned public per-geometry reference metadata for the planning
    worker: for each configured `measurement_geometries` entry, the same
    `reference_strategy()` + `canonical_sha256()` pair the supervisor
    independently re-runs during `validate_stage_request()`. Frozen once at
    session init (`autoresearch_init._load_v3_stage_contract`) into
    `state.stage_contract.geometry_references` so the worker never needs to
    execute code to learn what its candidate will be checked against; the
    supervisor still recomputes and compares on every validation -- this is
    published expectation, not a trusted substitute."""
    return [
        {
            "geometry_id": geometry["geometry_id"],
            "resolved_sha256": canonical_sha256(
                reference_strategy({"stage_contract": contract}, geometry["geometry_id"])
            ),
        }
        for geometry in contract["measurement_geometries"]
    ]


def reference_strategy(state: dict[str, Any], geometry_id: str) -> dict[str, Any]:
    strategy = copy.deepcopy(state["stage_contract"]["starting_strategy"]["strategy"])
    geometry = next(
        (
            g
            for g in state["stage_contract"]["measurement_geometries"]
            if g["geometry_id"] == geometry_id
        ),
        None,
    )
    if geometry is None:
        raise StageContractError("geometry is not configured")
    binding = _binding(state["stage_contract"], "symmetric_measurement_geometry")
    for target in binding["targets"]:
        instance = _find_instance(strategy["raw_spec"], target)
        parameter_name = target["parameter_name"]
        if parameter_name != "distance.multiplier" or not isinstance(
            instance.get("distance"), dict
        ):
            raise StageContractError("geometry binding must target distance.multiplier")
        instance["distance"]["multiplier"] = geometry["distance"]
    return strategy


def _strip_allowed(
    strategy: dict[str, Any], contract: dict[str, Any], dimensions: list[str]
) -> dict[str, Any]:
    value = copy.deepcopy(strategy)
    for dimension in dimensions:
        binding = _binding(contract, dimension)
        if dimension == "symmetric_measurement_geometry":
            for target in binding["targets"]:
                parameter = target["parameter_name"]
                instance = _find_instance(value["raw_spec"], target)
                if parameter != "distance.multiplier" or not isinstance(
                    instance.get("distance"), dict
                ):
                    raise StageContractError("geometry binding must target distance.multiplier")
                instance["distance"]["multiplier"] = "<mutable>"
        else:
            target = binding["targets"][0]
            matches = [
                x
                for x in _instances(value["raw_spec"], target)
                if x.get("component_id") == target["component_id"]
                and x.get("instance_id") == target["instance_id"]
            ]
            if not matches:
                continue
            if len(matches) != 1:
                raise StageContractError(f"bound {dimension} component is ambiguous")
            component = matches[0]
            parameter_container = (
                component.setdefault("params", {})
                if target["params_storage"] == "nested"
                else component
            )
            parameter = target["parameter_name"]
            if parameter not in parameter_container:
                raise StageContractError(f"bound parameter {parameter} is absent")
            parameter_container[parameter] = "<mutable>"
            params = {
                **target["fixed_parameters"],
                parameter: "<mutable>",
            }
            expected_fixed = {
                "component_id": target["component_id"],
                "instance_id": target["instance_id"],
            }
            if target["params_storage"] == "nested":
                expected_fixed["params"] = params
            else:
                expected_fixed.update(params)
            if component != expected_fixed:
                raise StageContractError(f"bound {dimension} component changes fixed fields")
            _instances(value["raw_spec"], target).remove(component)
    raw = value["raw_spec"]
    for key in ("setups",):
        if isinstance(raw.get(key), list):
            raw[key].sort(
                key=lambda item: (
                    str(item.get("instance_id", "")),
                    str(item.get("component_id", "")),
                )
            )
    blockers = raw.get("components", {}).get("blockers")
    if isinstance(blockers, list):
        blockers.sort(
            key=lambda item: (str(item.get("instance_id", "")), str(item.get("component_id", "")))
        )
    policy = raw.get("trade_management", {}).get("exit_policy", {})
    for group in [
        policy.get("always_on", {}),
        *[
            policy.get("profiles", {}).get(name, {})
            for name in ("aligned", "countertrend", "neutral")
        ],
    ]:
        if isinstance(group.get("exits"), list):
            group["exits"].sort(
                key=lambda item: (
                    str(item.get("instance_id", "")),
                    str(item.get("component_id", "")),
                )
            )
    return value


def validate_stage_request(
    request: BatchExperimentRequest, plan: dict[str, Any], state: dict[str, Any]
) -> None:
    context = plan["stage_context"]
    validate_stage_context(context, state)
    stage = context["active_stage"]
    geometry_id = context["geometry_id"]
    if stage == "A_BASELINE" and geometry_id in {
        r["geometry_id"] for r in state["phase_a_references"]
    }:
        raise StageContractError("Phase-A geometry already has an accepted reference")
    if stage != "A_BASELINE" and geometry_id not in {
        r["geometry_id"] for r in state["phase_a_references"]
    }:
        raise StageContractError("B stage requires a completed Phase-A geometry reference")
    reference = reference_strategy(state, geometry_id)
    if canonical_sha256(reference) != context["reference_strategy_sha256"]:
        raise StageContractError("reference strategy hash is inconsistent")
    if stage == "A_BASELINE" and len(request.candidates) != 1:
        raise StageContractError("A_BASELINE requires exactly one candidate")
    allowed = list(STAGE_DIMENSIONS[stage])
    contract = state["stage_contract"]
    expected = _strip_allowed(reference, contract, allowed)
    for candidate in request.candidates:
        actual = candidate.strategy.model_dump(mode="json")
        geometry_binding = _binding(contract, "symmetric_measurement_geometry")
        for target in geometry_binding["targets"]:
            actual_exit = _find_instance(actual["raw_spec"], target)
            reference_exit = _find_instance(reference["raw_spec"], target)
            if actual_exit.get("distance", {}).get("multiplier") != reference_exit.get(
                "distance", {}
            ).get("multiplier"):
                raise StageContractError(
                    "candidate geometry differs from configured/reference geometry"
                )
        if _strip_allowed(actual, contract, allowed) != expected:
            raise StageContractError("candidate changes a field outside active semantic dimensions")


def validate_disposition(value: dict[str, Any], active_stage: str) -> None:
    _exact(value, {"stage", "status", "evidence"}, "stage disposition")
    if value["stage"] != active_stage or value["status"] not in DISPOSITIONS:
        raise StageContractError("stage disposition identity/status is invalid")
    if not isinstance(value["evidence"], list) or (
        value["status"] != "in_progress" and not value["evidence"]
    ):
        raise StageContractError("closing stage disposition requires evidence")
    try:
        for item in value["evidence"]:
            EvidenceRef.model_validate(item)
    except ValidationError as exc:
        raise StageContractError(f"stage disposition evidence is invalid: {exc}") from exc
