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
