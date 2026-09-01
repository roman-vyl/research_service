"""Volume-persistence contract: runs/configs must survive a container recreate.

A container recreate destroys everything except mounted volumes. This
simulates that by pointing two independently-built ``create_app()``
instances (standing in for "old container" / "new container") at the same
host directories and confirming the second instance reads what the first
one wrote, with no shared in-process state between them.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.ports.strategy_engine import StrategyAuthoringValidationResult
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import FakeMarketData, FakeStrategyEngine, market_frame, strategy_identity


class ValidatingStrategyEngine:
    """Only implements what config validation needs."""

    def validate_authoring_config(
        self, strategy_id: str, instances: list[dict[str, Any]]
    ) -> StrategyAuthoringValidationResult:
        return StrategyAuthoringValidationResult(valid=True, errors=())

    def close(self) -> None:
        pass


def test_persisted_run_survives_container_recreate(tmp_path: Path) -> None:
    from test_single_instance_backtest import strategy_projection

    settings = Settings(artifacts_root=tmp_path / "runs", configs_root=tmp_path / "configs")
    old_container = Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(strategy_projection()),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    old_client = TestClient(create_app(old_container.settings, old_container))
    response = old_client.post(
        "/api/research/backtests",
        json={
            "strategy": {"enabled": True, **strategy_identity().model_dump(mode="json")},
            "range": ExplicitRange(from_ms=0, to_ms=900_000).model_dump(mode="json"),
            "execution": ExecutionPolicy().model_dump(mode="json"),
            "accounting": AccountingPolicy(
                initial_equity=Decimal("100"),
                entry_fee_rate=Decimal("0"),
                exit_fee_rate=Decimal("0"),
            ).model_dump(mode="json"),
            "managed_policy_enabled": False,
        },
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]

    # New container: fresh process wiring, same host-mounted directories.
    new_container = Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(strategy_projection()),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    new_client = TestClient(create_app(new_container.settings, new_container))
    detail = new_client.get(f"/api/research/runs/{run_id}")

    assert detail.status_code == 200
    assert detail.json()["manifest"]["run_id"] == run_id


def test_saved_config_survives_container_recreate(tmp_path: Path) -> None:
    settings = Settings(artifacts_root=tmp_path / "runs", configs_root=tmp_path / "configs")
    old_container = Container(
        settings=settings,
        strategy_engine=ValidatingStrategyEngine(),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    old_client = TestClient(create_app(old_container.settings, old_container))
    draft_payload = {
        "config_version": 1,
        "experiment_id": "baseline",
        "strategy_id": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0004},
        "instances": [
            {
                "enabled": True,
                "strategy_id": "ema_pullback",
                "ticker": "BTCUSDT.P",
                "base_timeframe": "5m",
                "raw_spec": {},
            }
        ],
    }
    save_response = old_client.post("/api/research/config/save", json={"draft": draft_payload})
    assert save_response.json()["ok"] is True

    new_container = Container(
        settings=settings,
        strategy_engine=ValidatingStrategyEngine(),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    new_client = TestClient(create_app(new_container.settings, new_container))
    state = new_client.get("/api/research/configs/state", params={"strategy_id": "ema_pullback"})

    assert state.status_code == 200
    assert state.json()["selected_experiment_id"] == "baseline"
    assert state.json()["draft"]["experiment_id"] == "baseline"
