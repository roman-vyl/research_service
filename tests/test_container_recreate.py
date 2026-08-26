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
from research_service.domain.execution import ExecutionPolicy
from research_service.ports.strategy_engine import StrategyAuthoringValidationResult
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import FakeMarketData, FakeStrategyEngine, market_frame, strategy_request


class ValidatingStrategyEngine:
    """Only implements what config validation needs."""

    def validate_authoring_config(
        self, family: str, instances: list[dict[str, Any]]
    ) -> StrategyAuthoringValidationResult:
        return StrategyAuthoringValidationResult(valid=True, errors=())

    def close(self) -> None:
        pass


def test_persisted_run_survives_container_recreate(tmp_path: Path) -> None:
    from test_single_instance_backtest import strategy_result

    settings = Settings(artifacts_root=tmp_path / "runs", configs_root=tmp_path / "configs")
    old_container = Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(strategy_result()),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    old_client = TestClient(create_app(old_container.settings, old_container))
    response = old_client.post(
        "/api/research/backtests",
        json={
            "run_id": "survives-recreate",
            "strategy": strategy_request().model_dump(mode="json"),
            "execution": ExecutionPolicy(quantity=Decimal("1")).model_dump(mode="json"),
            "accounting": AccountingPolicy(
                initial_equity=Decimal("100"),
                entry_fee_rate=Decimal("0"),
                exit_fee_rate=Decimal("0"),
            ).model_dump(mode="json"),
            "managed_policy_enabled": False,
        },
    )
    assert response.status_code == 201

    # New container: fresh process wiring, same host-mounted directories.
    new_container = Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(strategy_result()),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path / "runs"),
    )
    new_client = TestClient(create_app(new_container.settings, new_container))
    detail = new_client.get("/api/research/runs/survives-recreate")

    assert detail.status_code == 200
    assert detail.json()["manifest"]["run_id"] == "survives-recreate"


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
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0004},
        "instances": [{"instance_id": "baseline", "strategy": {}}],
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
    state = new_client.get("/api/research/configs/state", params={"family": "ema_pullback"})

    assert state.status_code == 200
    assert state.json()["selected_experiment_id"] == "baseline"
    assert state.json()["draft"]["experiment_id"] == "baseline"
