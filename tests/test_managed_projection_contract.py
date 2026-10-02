"""`historical-managed-projection-cutover-v1` group 1: Research decodes
Strategy Engine's final `HistoricalManagedProjection` wire contract
(baseline 07ff911) -- a `phase_transition` rule carries exactly one of
`condition_id`, (`distance_id`, `trade_metric`) or `paths` -- and fails
decode on any dangling `condition_id`/`distance_id` reference.

The wire dicts below mirror `strategy_serialization.py::_serialize_rule`
on the Strategy Engine side: atomic rules carry no `paths` key; a
composite rule carries all three atomic references as null plus `paths`.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from research_service.adapters.http.strategy_engine_client import (
    parse_historical_execution_projection,
)
from research_service.domain.contracts import HistoricalManagedProjectionDTO
from research_service.domain.errors import UpstreamServiceError

_N = 3


def _series() -> dict[str, list[bool]]:
    return {"long": [False] * _N, "short": [False] * _N}


def _wire(rules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "conditions": {"adx5": _series(), "adx1h": _series(), "di1h": _series(), "rsi": _series()},
        "distances": {"mfe3atr": [None, 1.0, 1.0], "bars5": [5.0] * _N, "be": [0.0] * _N},
        "rules": rules,
    }


def _composite_rule(**path_overrides: Any) -> dict[str, Any]:
    path: dict[str, Any] = {
        "path_id": "fast",
        "condition_id": "adx5",
        "thresholds": [{"distance_id": "mfe3atr", "trade_metric": "mfe_distance"}],
        "at_least": None,
    }
    path.update(path_overrides)
    return {
        "kind": "phase_transition",
        "rule_id": "to_proven",
        "target_phase": "proven",
        "condition_id": None,
        "distance_id": None,
        "trade_metric": None,
        "paths": [
            path,
            {
                "path_id": "htf",
                "condition_id": None,
                "thresholds": [],
                "at_least": {
                    "k": 2,
                    "terms": [
                        {"condition_id": "adx1h", "distance_id": None, "trade_metric": None},
                        {"condition_id": "di1h", "distance_id": None, "trade_metric": None},
                        {"condition_id": None, "distance_id": "bars5", "trade_metric": "bars_since_entry"},
                    ],
                },
            },
        ],
    }


def _atomic_rules() -> list[dict[str, Any]]:
    return [
        {
            "kind": "phase_transition",
            "rule_id": "adx_gate",
            "target_phase": "proven",
            "condition_id": "adx5",
            "distance_id": None,
            "trade_metric": None,
        },
        {
            "kind": "phase_transition",
            "rule_id": "mfe_gate",
            "target_phase": "protected",
            "condition_id": None,
            "distance_id": "mfe3atr",
            "trade_metric": "mfe_distance",
        },
        {"kind": "stop_action", "rule_id": "be", "activation_phase": "proven", "distance_id": "be"},
        {
            "kind": "take_action",
            "rule_id": "tp_off",
            "activation_phase": "proven",
            "resulting_profile": "disable_initial_tp",
        },
        {
            "kind": "runtime_exit",
            "rule_id": "rsi_exit",
            "activation_phase": "initial_risk",
            "condition_id": "rsi",
            "confirm_bars": 1,
            "exit_class": "runtime_close",
        },
    ]


def test_composite_rule_decodes() -> None:
    dto = HistoricalManagedProjectionDTO.model_validate(_wire([_composite_rule()]))

    rule = dto.rules[0]
    assert rule.kind == "phase_transition"
    assert rule.condition_id is None and rule.distance_id is None
    assert rule.paths is not None
    assert [path.path_id for path in rule.paths] == ["fast", "htf"]
    htf = rule.paths[1]
    assert htf.at_least is not None and htf.at_least.k == 2
    assert htf.at_least.terms[2].trade_metric == "bars_since_entry"


def test_atomic_rules_decode_unchanged() -> None:
    dto = HistoricalManagedProjectionDTO.model_validate(_wire(_atomic_rules()))

    phase_rules = [rule for rule in dto.rules if rule.kind == "phase_transition"]
    assert [rule.paths for rule in phase_rules] == [None, None]
    assert [rule.kind for rule in dto.rules] == [
        "phase_transition",
        "phase_transition",
        "stop_action",
        "take_action",
        "runtime_exit",
    ]
    stop = dto.rules[2]
    assert stop.kind == "stop_action"
    assert stop.stop_formula == "entry_offset"
    assert stop.trigger_distance_id is None
    serialized = dto.model_dump(mode="json")
    serialized_stop = serialized["rules"][2]
    assert "stop_formula" not in serialized_stop
    assert "trigger_distance_id" not in serialized_stop


@pytest.mark.parametrize("formula", ["initial_r_lock", "initial_r_trailing"])
def test_initial_r_stop_formulas_decode_with_opaque_references(formula: str) -> None:
    wire = _wire(
        [
            {
                "kind": "stop_action",
                "rule_id": "r-stop",
                "activation_phase": "initial_risk",
                "distance_id": "be",
                "stop_formula": formula,
                "trigger_distance_id": "bars5",
            }
        ]
    )

    (rule,) = HistoricalManagedProjectionDTO.model_validate(wire).rules
    assert rule.kind == "stop_action"
    assert rule.stop_formula == formula
    assert rule.trigger_distance_id == "bars5"
    serialized_rule = HistoricalManagedProjectionDTO.model_validate(wire).model_dump(mode="json")[
        "rules"
    ][0]
    assert serialized_rule["stop_formula"] == formula
    assert serialized_rule["trigger_distance_id"] == "bars5"


@pytest.mark.parametrize(
    "rule",
    [
        {
            "kind": "stop_action",
            "rule_id": "bad",
            "activation_phase": "initial_risk",
            "distance_id": "be",
            "stop_formula": "entry_offset",
            "trigger_distance_id": "bars5",
        },
        {
            "kind": "stop_action",
            "rule_id": "bad",
            "activation_phase": "initial_risk",
            "distance_id": "be",
            "stop_formula": "initial_r_lock",
        },
        {
            "kind": "stop_action",
            "rule_id": "bad",
            "activation_phase": "initial_risk",
            "distance_id": "be",
            "stop_formula": "strategy_component_name",
        },
    ],
)
def test_stop_formula_field_invariants_fail_decode(rule: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


def test_dangling_stop_trigger_reference_fails_decode() -> None:
    rule = {
        "kind": "stop_action",
        "rule_id": "r-stop",
        "activation_phase": "initial_risk",
        "distance_id": "be",
        "stop_formula": "initial_r_trailing",
        "trigger_distance_id": "missing",
    }
    with pytest.raises(ValidationError, match="unknown ids"):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


@pytest.mark.parametrize(
    "overrides",
    [
        # two references at once
        {"condition_id": "adx5"},
        {"distance_id": "mfe3atr", "trade_metric": "mfe_distance"},
        # partial distance reference alongside paths
        {"distance_id": "mfe3atr"},
        # empty paths is not a reference
        {"paths": []},
    ],
)
def test_phase_rule_xor_violations_fail(overrides: dict[str, Any]) -> None:
    rule = _composite_rule()
    rule.update(overrides)
    with pytest.raises(ValidationError):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


def test_phase_rule_with_no_reference_fails() -> None:
    rule = _composite_rule()
    rule.pop("paths")
    with pytest.raises(ValidationError):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


@pytest.mark.parametrize(
    "term",
    [
        {"condition_id": "adx1h", "distance_id": "bars5", "trade_metric": "bars_since_entry"},
        {"condition_id": None, "distance_id": "bars5", "trade_metric": None},
        {"condition_id": None, "distance_id": None, "trade_metric": None},
    ],
)
def test_at_least_term_xor_violations_fail(term: dict[str, Any]) -> None:
    rule = _composite_rule(at_least={"k": 1, "terms": [term]})
    with pytest.raises(ValidationError):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


def test_at_least_k_above_terms_fails() -> None:
    rule = _composite_rule(
        at_least={
            "k": 2,
            "terms": [{"condition_id": "adx1h", "distance_id": None, "trade_metric": None}],
        }
    )
    with pytest.raises(ValidationError):
        HistoricalManagedProjectionDTO.model_validate(_wire([rule]))


def _dangling(kind: str) -> list[dict[str, Any]]:
    rules = _atomic_rules()
    if kind == "atomic_condition":
        rules[0]["condition_id"] = "missing"
    elif kind == "atomic_distance":
        rules[1]["distance_id"] = "missing"
    elif kind == "path_condition":
        rules.append(_composite_rule(condition_id="missing"))
    elif kind == "path_threshold_distance":
        rules.append(
            _composite_rule(thresholds=[{"distance_id": "missing", "trade_metric": "mfe_pct"}])
        )
    elif kind == "at_least_condition_term":
        rules.append(
            _composite_rule(
                at_least={
                    "k": 1,
                    "terms": [{"condition_id": "missing", "distance_id": None, "trade_metric": None}],
                }
            )
        )
    elif kind == "at_least_distance_term":
        rules.append(
            _composite_rule(
                at_least={
                    "k": 1,
                    "terms": [{"condition_id": None, "distance_id": "missing", "trade_metric": "mfe_pct"}],
                }
            )
        )
    elif kind == "stop_distance":
        rules[2]["distance_id"] = "missing"
    elif kind == "runtime_condition":
        rules[4]["condition_id"] = "missing"
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(kind)
    return rules


@pytest.mark.parametrize(
    "kind",
    [
        "atomic_condition",
        "atomic_distance",
        "path_condition",
        "path_threshold_distance",
        "at_least_condition_term",
        "at_least_distance_term",
        "stop_distance",
        "runtime_condition",
    ],
)
def test_every_dangling_reference_kind_fails_decode(kind: str) -> None:
    with pytest.raises(ValidationError, match="unknown ids"):
        HistoricalManagedProjectionDTO.model_validate(_wire(_dangling(kind)))


def _projection_body(managed: dict[str, Any]) -> dict[str, Any]:
    profiles = {"aligned": [], "countertrend": [], "neutral": []}
    return {
        "contract_version": "strategy_evaluation_execution.v2",
        "strategy_id": "ema_pullback",
        "config_hash": "c",
        "market": {
            "ticker": "BTCUSDT.P",
            "base_timeframe": "5m",
            "from_ms": 0,
            "to_ms": 900_000,
            "market_data_hash": "h",
            "bar_count": _N,
        },
        "entry_opportunities": [],
        "signal_exit_events": {"long": dict(profiles), "short": dict(profiles)},
        "warnings": [],
        "managed": managed,
    }


def test_composite_projection_decodes_through_the_http_parser() -> None:
    projection = parse_historical_execution_projection(
        _projection_body(_wire(_atomic_rules() + [_composite_rule()]))
    )

    assert projection.managed is not None
    assert projection.managed.rules[-1].kind == "phase_transition"


def test_dangling_reference_surfaces_as_upstream_contract_error() -> None:
    with pytest.raises(UpstreamServiceError) as exc_info:
        parse_historical_execution_projection(
            _projection_body(_wire(_dangling("path_threshold_distance")))
        )

    errors = exc_info.value.details["errors"]
    assert [error["loc"] for error in errors] == [("managed",)]
    assert "unknown ids" in errors[0]["msg"]
