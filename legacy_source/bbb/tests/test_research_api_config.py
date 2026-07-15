"""Research API BFF — component catalog and config draft endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from research_api.main import app
from research_api.services import config_service


def _valid_draft() -> dict[str, object]:
    return {
        "config_version": 1,
        "experiment_id": "api_config_smoke",
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0006, "slippage": 0.0001},
        "instances": [
            {
                "instance_id": "baseline",
                "variant": "baseline",
                "market": {"symbol": "BTCUSDT", "base_timeframe": "5m"},
                "strategy": {
                    "trade_sides": {"long": True, "short": False},
                    "anchor_stack": {
                        "source": "close",
                        "timeframe": "base",
                        "fast": 100,
                        "anchor": 200,
                        "slow": 1000,
                    },
                    "direction": {"component_id": "ema_anchor_stack_trend"},
                    "setups": [
                        {
                            "instance_id": "setup",
                            "component_id": "untouched_anchor_setup",
                            "lookback": 50,
                            "active_bars": 3,
                        }
                    ],
                    "trigger": {"component_id": "reclaim_anchor"},
                    "blockers": [{"instance_id": "no_blockers", "component_id": "no_blockers"}],
                    "risk": {"component_id": "no_risk_filter"},
                    "contexts": {},
                    "trade_management": {
                        "exit_policy": {
                            "always_on": {
                                "exits": [
                                    {
                                        "instance_id": "atr_sl",
                                        "component_id": "atr_stop_loss",
                                        "distance": {"timeframe": "base", "period": 14, "multiplier": 1.5},
                                    },
                                    {
                                        "instance_id": "atr_tp",
                                        "component_id": "atr_take_profit",
                                        "distance": {"timeframe": "base", "period": 14, "multiplier": 4.0},
                                    },
                                ]
                            },
                            "profiles": {
                                "aligned": {"exits": []},
                                "countertrend": {"exits": []},
                                "neutral": {"exits": []},
                            },
                        }
                    },
                },
            }
        ],
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_component_catalog_returns_ema_pullback_components(client: TestClient) -> None:
    res = client.get("/api/research/component-catalog?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    assert body["family"] == "ema_pullback"
    assert any(
        c["component_id"] == "rsi_lookback_extreme_blocker" for c in body["components"]
    )
    setup_components = [c for c in body["components"] if c.get("role") == "setup"]
    assert [c["component_id"] for c in setup_components] == [
        "untouched_anchor_setup",
        "ema_bounce_counter_setup",
        "anchor_stack_width_setup",
    ]
    params = setup_components[0]["params_schema"]
    assert set(params) == {"lookback", "active_bars"}
    assert params["lookback"]["default"] == 50
    assert params["active_bars"]["default"] == 3
    bounce_params = setup_components[1]["params_schema"]
    assert set(bounce_params) == {
        "max_bounces",
        "raw_touch_mode",
        "touch_lookback_bars",
        "trend_start_confirmation_bars",
        "trend_break_confirmation_bars",
    }
    assert "anchor_stack" in setup_components[1]["description"]
    assert bounce_params["raw_touch_mode"]["enum"] == ["range_cross"]
    assert setup_components[1].get("params_storage") == "nested"
    assert all(component.get("supports_context_consumption") is True for component in setup_components)
    width_setup = next(
        c for c in setup_components if c["component_id"] == "anchor_stack_width_setup"
    )
    assert "1h" in width_setup["params_schema"]["atr_timeframe"]["enum"]
    for component in setup_components:
        setup_policy_ids = [
            p["policy_id"] for p in component.get("context_consumption_policies") or []
        ]
        assert "htf_regime_gate" in setup_policy_ids
    reclaim_components = [c for c in body["components"] if c.get("component_id") == "reclaim_anchor"]
    assert len(reclaim_components) == 1
    reclaim_params = reclaim_components[0]["params_schema"]
    assert reclaim_params["lookback"]["default"] == 1
    assert reclaim_params["lookback"]["min"] == 1
    strong_components = [
        c for c in body["components"] if c.get("component_id") == "strong_reclaim_anchor"
    ]
    assert len(strong_components) == 1
    strong_params = strong_components[0]["params_schema"]
    assert strong_params["lookback"]["default"] == 1
    assert strong_params["lookback"]["min"] == 1
    assert all(c["component_id"] != "htf_context" for c in body["components"])
    assert any(s["section_id"] == "strategy_contexts" for s in body["sections"])
    assert not any(s["section_id"] == "exit_policy_context" for s in body["sections"])
    providers = body.get("context_providers") or []
    assert any(p["component_id"] == "htf_context" for p in providers)
    roles = body.get("context_consumption_roles") or []
    exit_role = next(r for r in roles if r["role"] == "exit_policy")
    assert any(p["policy_id"] == "exit_profile_by_htf_state" for p in exit_role["policies"])
    close_loss = next(c for c in body["components"] if c["component_id"] == "ema_close_loss_exit")
    assert close_loss["params_schema"]["confirm_bars"]["default"] == 1
    assert "ema.timeframe" in close_loss["params_schema"]
    cross_loss = next(c for c in body["components"] if c["component_id"] == "ema_cross_loss_exit")
    assert cross_loss["params_schema"]["confirm_bars"]["default"] == 1
    assert cross_loss["params_schema"]["fast_ema.timeframe"]["default"] == "base"


def test_component_catalog_excludes_deprecated_break_even_stop_authoring(
    client: TestClient,
) -> None:
    res = client.get("/api/research/component-catalog?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    assert not any(c["component_id"] == "break_even_stop" for c in body["components"])


def test_validate_config_ok(client: TestClient) -> None:
    res = client.post("/api/research/config/validate", json=_valid_draft())
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["errors"] == []


def test_component_catalog_strategy_contexts_section(client: TestClient) -> None:
    res = client.get("/api/research/component-catalog?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    section_ids = [s["section_id"] for s in body["sections"]]
    assert "strategy_contexts" in section_ids
    assert "exit_policy_context" not in section_ids
    assert any(p["component_id"] == "htf_context" for p in body["context_providers"])
    exit_roles = [r for r in body["context_consumption_roles"] if r["role"] == "exit_policy"]
    assert len(exit_roles) == 1
    assert exit_roles[0]["policies"][0]["policy_id"] == "exit_profile_by_htf_state"
    rsi_blocker = next(
        c for c in body["components"] if c["component_id"] == "rsi_lookback_extreme_blocker"
    )
    assert rsi_blocker.get("supports_context_consumption") is True
    blocker_roles = [r for r in body["context_consumption_roles"] if r["role"] == "blockers"]
    assert len(blocker_roles) == 1
    blocker_policy_ids = [p["policy_id"] for p in blocker_roles[0]["policies"]]
    assert "htf_state_gate" not in blocker_policy_ids
    assert "htf_regime_gate" in blocker_policy_ids
    counter_candle = next(c for c in body["components"] if c["component_id"] == "counter_candle_blocker")
    policy_ids = [p["policy_id"] for p in counter_candle.get("context_consumption_policies") or []]
    assert "htf_regime_gate" in policy_ids
    regime_policy = next(
        p for p in counter_candle["context_consumption_policies"] if p["policy_id"] == "htf_regime_gate"
    )
    assert "allowed_regimes" in regime_policy["params_schema"]
    assert regime_policy["params_schema"]["allowed_regimes"]["enum"] == [
        "aligned",
        "countertrend",
        "neutral",
    ]
    no_blockers = next(c for c in body["components"] if c["component_id"] == "no_blockers")
    assert no_blockers.get("supports_context_consumption") is not True
    setup_roles = [r for r in body["context_consumption_roles"] if r["role"] == "setup"]
    assert len(setup_roles) == 1
    assert [p["policy_id"] for p in setup_roles[0]["policies"]] == ["htf_regime_gate"]


def test_validate_rejects_htf_state_gate_on_blocker(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["contexts"] = {
        "htf": {
            "component_id": "htf_context",
            "timeframe": "4h",
            "source": "close",
            "fast_period": 100,
            "anchor_period": 200,
            "slow_period": 1000,
        }
    }
    strategy["blockers"] = [
        {
            "instance_id": "ccb",
            "component_id": "counter_candle_blocker",
            "context_consumption": {
                "context_ref": "htf",
                "policy": {
                    "policy_id": "htf_state_gate",
                    "params": {"allowed_states": ["up"]},
                },
            },
        }
    ]
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any("htf_state_gate" in (e.get("message") or "") for e in body["errors"])


def test_validate_rejects_exit_policy_context(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    trade_management = dict(strategy["trade_management"])  # type: ignore[arg-type]
    exit_policy = dict(trade_management["exit_policy"])  # type: ignore[arg-type]
    exit_policy["context"] = {
        "component_id": "htf_context",
        "timeframe": "4h",
        "source": "close",
        "fast_period": 100,
        "anchor_period": 200,
        "slow_period": 1000,
    }
    trade_management["exit_policy"] = exit_policy
    strategy["trade_management"] = trade_management
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any("exit_policy.context" in e["message"] for e in body["errors"])


def test_validate_rejects_profile_exits_without_consumption(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["contexts"] = {
        "htf": {
            "component_id": "htf_context",
            "timeframe": "4h",
            "source": "close",
            "fast_period": 100,
            "anchor_period": 200,
            "slow_period": 1000,
        }
    }
    trade_management = dict(strategy["trade_management"])  # type: ignore[arg-type]
    exit_policy = dict(trade_management["exit_policy"])  # type: ignore[arg-type]
    profiles = dict(exit_policy["profiles"])  # type: ignore[arg-type]
    profiles["aligned"] = {
        "exits": [{"instance_id": "profile_exit", "component_id": "no_signal_exit"}]
    }
    exit_policy["profiles"] = profiles
    trade_management["exit_policy"] = exit_policy
    strategy["trade_management"] = trade_management
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(
        "context_consumption" in (e.get("path") or "")
        and "required" in (e.get("message") or "")
        for e in body["errors"]
    )


def test_validate_setup_context_consumption_has_structured_path(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["contexts"] = {
        "htf": {
            "component_id": "htf_context",
            "timeframe": "4h",
            "source": "close",
            "fast_period": 100,
            "anchor_period": 200,
            "slow_period": 1000,
        }
    }
    setups = list(strategy["setups"])  # type: ignore[arg-type]
    setup = dict(setups[0])  # type: ignore[arg-type]
    setup["context_consumption"] = {
        "context_ref": "htf",
        "policy": {"policy_id": "htf_state_gate", "params": {}},
    }
    setups[0] = setup
    strategy["setups"] = setups
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any("setups" in (e.get("path") or "") for e in body["errors"])


def test_validate_rejects_unknown_context_ref(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["contexts"] = {
        "htf": {
            "component_id": "htf_context",
            "timeframe": "4h",
            "source": "close",
            "fast_period": 100,
            "anchor_period": 200,
            "slow_period": 1000,
        }
    }
    trade_management = dict(strategy["trade_management"])  # type: ignore[arg-type]
    exit_policy = dict(trade_management["exit_policy"])  # type: ignore[arg-type]
    profiles = dict(exit_policy["profiles"])  # type: ignore[arg-type]
    profiles["aligned"] = {
        "exits": [{"instance_id": "profile_exit", "component_id": "no_signal_exit"}]
    }
    exit_policy["profiles"] = profiles
    exit_policy["context_consumption"] = {
        "context_ref": "missing_ref",
        "policy": {"policy_id": "exit_profile_by_htf_state", "params": {}},
    }
    trade_management["exit_policy"] = exit_policy
    strategy["trade_management"] = trade_management
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any("missing_ref" in e["message"] for e in body["errors"])


def test_validate_config_rejects_exit_policy_context(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    trade_management = dict(strategy["trade_management"])  # type: ignore[arg-type]
    exit_policy = dict(trade_management["exit_policy"])  # type: ignore[arg-type]
    exit_policy["context"] = {
        "component_id": "htf_context",
        "timeframe": "4h",
        "source": "close",
        "fast_period": 100,
        "anchor_period": 200,
        "slow_period": 1000,
    }
    trade_management["exit_policy"] = exit_policy
    strategy["trade_management"] = trade_management
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any("exit_policy.context" in e["message"] for e in body["errors"])


def test_validate_config_rejects_profile_exits_without_consumption(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["contexts"] = {
        "htf": {
            "component_id": "htf_context",
            "timeframe": "4h",
            "source": "close",
            "fast_period": 100,
            "anchor_period": 200,
            "slow_period": 1000,
        },
    }
    trade_management = dict(strategy["trade_management"])  # type: ignore[arg-type]
    exit_policy = dict(trade_management["exit_policy"])  # type: ignore[arg-type]
    profiles = dict(exit_policy["profiles"])  # type: ignore[arg-type]
    profiles["aligned"] = {
        "exits": [{"instance_id": "rsi_exit", "component_id": "rsi_signal_exit"}],
    }
    exit_policy["profiles"] = profiles
    trade_management["exit_policy"] = exit_policy
    strategy["trade_management"] = trade_management
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(
        e.get("path") == "trade_management.exit_policy.context_consumption"
        for e in body["errors"]
    )


def test_validate_config_rejects_bad_instance(client: TestClient) -> None:
    draft = _valid_draft()
    instances = list(draft["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    strategy = dict(inst["strategy"])  # type: ignore[arg-type]
    strategy["trigger"] = {"component_id": "unknown_trigger"}
    inst["strategy"] = strategy
    instances[0] = inst
    draft["instances"] = instances

    res = client.post("/api/research/config/validate", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["errors"]


def test_serialize_invalid_draft_returns_requested_format(client: TestClient) -> None:
    draft = _valid_draft()
    draft["experiment_id"] = ""

    res = client.post("/api/research/config/serialize?format=yaml", json=draft)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["format"] == "yaml"
    assert body["content"] == ""


def test_serialize_config_json(client: TestClient) -> None:
    res = client.post("/api/research/config/serialize?format=json", json=_valid_draft())
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["format"] == "json"
    parsed = json.loads(body["content"])
    assert parsed["schema_version"] == 1
    assert parsed["experiment_id"] == "api_config_smoke"


def test_save_config_writes_file(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configs_root = tmp_path / "configs"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)

    res = client.post(
        "/api/research/config/save",
        json={"draft": _valid_draft()},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["path"] is not None
    saved = configs_root / "ema_pullback" / "api_config_smoke.json"
    assert saved.exists()
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["family"] == "ema_pullback"


def test_save_config_rejects_invalid_draft(client: TestClient) -> None:
    draft = _valid_draft()
    draft["experiment_id"] = ""

    res = client.post("/api/research/config/save", json={"draft": draft})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["path"] is None


@pytest.mark.parametrize(
    "family",
    [
        "unknown_family",
        "../ema_pullback",
        "ema_pullback/../../../etc",
        "foo/bar",
    ],
)
def test_config_state_rejects_bad_family(client: TestClient, family: str) -> None:
    res = client.get(f"/api/research/configs/state?family={family}")
    assert res.status_code == 400
    assert "unsupported family" in res.json()["detail"]


@pytest.mark.parametrize(
    "family",
    [
        "unknown_family",
        "../ema_pullback",
        "ema_pullback/foo",
    ],
)
def test_select_config_rejects_bad_family(client: TestClient, family: str) -> None:
    res = client.put(
        "/api/research/configs/selected",
        json={"family": family, "experiment_id": "any"},
    )
    assert res.status_code == 400
    assert "unsupported family" in res.json()["detail"]


def test_save_config_selects_saved_ema_pullback(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs_root = tmp_path / "configs"
    selection_file = configs_root / ".workbench_selection.json"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)
    monkeypatch.setattr(config_service, "_SELECTION_FILE", selection_file)

    res = client.post("/api/research/config/save", json={"draft": _valid_draft()})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert selection_file.is_file()
    store = json.loads(selection_file.read_text(encoding="utf-8"))
    assert store["ema_pullback"] == "api_config_smoke"


def test_config_state_empty(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configs_root = tmp_path / "configs"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)
    monkeypatch.setattr(config_service, "_SELECTION_FILE", configs_root / ".workbench_selection.json")

    res = client.get("/api/research/configs/state?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    assert body["family"] == "ema_pullback"
    assert body["configs"] == []
    assert body["draft"] is None


def test_config_state_loads_saved_config(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs_root = tmp_path / "configs"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)
    monkeypatch.setattr(config_service, "_SELECTION_FILE", configs_root / ".workbench_selection.json")

    save = client.post("/api/research/config/save", json={"draft": _valid_draft()})
    assert save.json()["ok"] is True

    res = client.get("/api/research/configs/state?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    assert len(body["configs"]) == 1
    assert body["selected_experiment_id"] == "api_config_smoke"
    assert body["draft"]["experiment_id"] == "api_config_smoke"
    assert body["draft"]["instances"][0]["instance_id"] == "baseline"


def test_select_config_switches_draft(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs_root = tmp_path / "configs"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)
    monkeypatch.setattr(config_service, "_SELECTION_FILE", configs_root / ".workbench_selection.json")

    first = _valid_draft()
    client.post("/api/research/config/save", json={"draft": first})

    second = _valid_draft()
    second["experiment_id"] = "api_config_alt"
    instances = list(second["instances"])  # type: ignore[index]
    inst = dict(instances[0])  # type: ignore[arg-type]
    inst["instance_id"] = "alt"
    inst["variant"] = "alt"
    instances[0] = inst
    second["instances"] = instances
    client.post("/api/research/config/save", json={"draft": second})

    res = client.put(
        "/api/research/configs/selected",
        json={"family": "ema_pullback", "experiment_id": "api_config_alt"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["selected_experiment_id"] == "api_config_alt"
    assert body["draft"]["instances"][0]["instance_id"] == "alt"


def test_config_state_tolerates_invalid_selected_draft(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs_root = tmp_path / "configs"
    family_dir = configs_root / "ema_pullback"
    family_dir.mkdir(parents=True)
    selection_file = configs_root / ".workbench_selection.json"
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)
    monkeypatch.setattr(config_service, "_SELECTION_FILE", selection_file)

    legacy_draft = {
        "schema_version": 1,
        "experiment_id": "legacy_exit_management",
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0},
        "instances": [
            {
                "instance_id": "baseline",
                "variant": "baseline",
                "market": {"symbol": "BTCUSDT", "base_timeframe": "5m"},
                "strategy": {
                    **_valid_draft()["instances"][0]["strategy"],  # type: ignore[index]
                    "trade_management": {
                        "exit_policy": {"always_on": {"exits": []}, "profiles": {}},
                        "exit_management": {
                            "always_on": {
                                "rules": [
                                    {
                                        "instance_id": "be",
                                        "component_id": "break_even_stop",
                                        "trigger_r": 1.0,
                                        "offset_r": 0.0,
                                        "apply_once": True,
                                    }
                                ]
                            }
                        },
                    },
                },
            }
        ],
    }
    (family_dir / "legacy_exit_management.json").write_text(
        json.dumps(legacy_draft), encoding="utf-8"
    )
    selection_file.write_text(
        json.dumps({"ema_pullback": "legacy_exit_management"}), encoding="utf-8"
    )

    res = client.get("/api/research/configs/state?family=ema_pullback")
    assert res.status_code == 200
    body = res.json()
    assert body["selected_experiment_id"] == "legacy_exit_management"
    assert body["draft"] is None
    assert len(body["configs"]) == 1
