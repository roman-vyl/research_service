from pathlib import Path
from fastapi.testclient import TestClient
from research_service.api.app import create_app
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from research_service.ports.strategy_engine import (
    StrategyAuthoringValidationResult,
    StrategyValidationError,
)


class Strategy:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def health(self):
        return True

    def validate_authoring_config(self, strategy_id, instances):
        self.calls.append((strategy_id, instances))
        return self.result


class Market:
    def health(self):
        return True


class Store:
    def __init__(self, p):
        self.root = p

    def ensure_ready(self):
        self.root.mkdir(parents=True, exist_ok=True)


def client(tmp_path, strategy):
    s = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(create_app(s, Container(s, strategy, Market(), Store(tmp_path))))


def draft():
    return {
        "config_version": 1,
        "experiment_id": "x",
        "strategy_id": "ema_pullback",
        "execution": {"init_cash": 10000, "fees": 0.0004, "slippage": 0},
        "instances": [
            {
                "enabled": True,
                "strategy_id": "ema_pullback",
                "ticker": "BTCUSDT.P",
                "base_timeframe": "5m",
                "raw_spec": {"anchor": {"period": 200}},
            }
        ],
    }


def test_delegates_strategy_semantics_and_preserves_result(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    r = client(tmp_path, strategy).post("/api/research/config/validate", json=draft())
    assert r.status_code == 200 and r.json() == {"ok": True, "errors": []}
    assert strategy.calls[0][0] == "ema_pullback"


def test_maps_strategy_errors(tmp_path: Path):
    strategy = Strategy(
        StrategyAuthoringValidationResult(
            False, (StrategyValidationError("instances[0].strategy", "bad"),)
        )
    )
    r = client(tmp_path, strategy).post("/api/research/config/validate", json=draft())
    assert r.json() == {
        "ok": False,
        "errors": [{"path": "instances[0].strategy", "message": "bad"}],
    }


def test_rejects_execution_before_upstream(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["execution"]["fees"] = -1
    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)
    assert r.json()["ok"] is False and strategy.calls == []


def _instance(strategy_id: str = "ema_pullback") -> dict:
    return {
        "enabled": True,
        "strategy_id": strategy_id,
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {"anchor": {"period": 200}},
    }


def test_single_matching_instance_strategy_id_accepted(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["instances"] = [_instance("ema_pullback")]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json() == {"ok": True, "errors": []}


def test_multiple_matching_instances_strategy_id_accepted(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["instances"] = [_instance("ema_pullback"), _instance("ema_pullback")]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json() == {"ok": True, "errors": []}


def test_single_mismatching_instance_strategy_id_rejected(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["instances"] = [_instance("some_other_strategy")]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json() == {
        "ok": False,
        "errors": [
            {
                "path": "instances[0].strategy_id",
                "message": (
                    "must match draft.strategy_id ('ema_pullback'); "
                    "got 'some_other_strategy'"
                ),
            }
        ],
    }
    # Envelope-level mismatch fails closed before delegating to Engine.
    assert strategy.calls == []


def _ema_instance_with_exit(*, instance_id: str | None) -> dict:
    rule: dict = {
        "component_id": "atr_stop_setup",
        "exit_kind": "stop",
        "distance": {"timeframe": "base", "period": 14, "multiplier": 1.5},
    }
    if instance_id is not None:
        rule["instance_id"] = instance_id
    return {
        "enabled": True,
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {
            "anchor_stack": {
                "fast": {"source": "close", "timeframe": "base", "period": 2},
                "anchor": {"source": "close", "timeframe": "base", "period": 3},
                "slow": {"source": "close", "timeframe": "base", "period": 5},
            },
            "components": {"blockers": []},
            "setups": [],
            "contexts": {},
            "trade_management": {
                "exit_policy": {
                    "always_on": {"exits": [rule]},
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


def test_atr_exit_without_instance_id_does_not_report_ok(tmp_path: Path):
    # Engine's authoritative semantic-validation contract rejects an exit
    # rule missing a rule instance_id; Research must reflect that, not
    # report success. See strategy_engine authoring-config validation.
    strategy = Strategy(
        StrategyAuthoringValidationResult(
            False,
            (StrategyValidationError("instances[0]", "exits[0].instance_id must be a non-empty string"),),
        )
    )
    payload = draft()
    payload["instances"] = [_ema_instance_with_exit(instance_id=None)]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json()["ok"] is False
    assert strategy.calls[0][0] == "ema_pullback"


def test_atr_exit_with_instance_id_reports_ok(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["instances"] = [_ema_instance_with_exit(instance_id="atr_stop_1")]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json() == {"ok": True, "errors": []}


def test_mismatch_among_multiple_instances_identifies_offending_index(tmp_path: Path):
    strategy = Strategy(StrategyAuthoringValidationResult(True, ()))
    payload = draft()
    payload["instances"] = [
        _instance("ema_pullback"),
        _instance("some_other_strategy"),
        _instance("ema_pullback"),
    ]

    r = client(tmp_path, strategy).post("/api/research/config/validate", json=payload)

    assert r.json() == {
        "ok": False,
        "errors": [
            {
                "path": "instances[1].strategy_id",
                "message": (
                    "must match draft.strategy_id ('ema_pullback'); "
                    "got 'some_other_strategy'"
                ),
            }
        ],
    }
    assert strategy.calls == []
