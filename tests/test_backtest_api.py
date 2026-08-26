from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.application.backtests import SingleInstanceBacktestRequest
from research_service.domain.execution import ExecutionPolicy
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_request,
    strategy_result,
)


def build_client(tmp_path: Path) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(
                settings=settings,
                strategy_engine=FakeStrategyEngine(strategy_result()),
                market_data=FakeMarketData(market_frame()),
                artifacts=FilesystemArtifactStore(tmp_path),
            ),
        )
    )


def payload(run_id: str) -> dict[str, object]:
    request = SingleInstanceBacktestRequest(
        run_id=run_id,
        strategy=strategy_request(),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )
    return request.model_dump(mode="json")


def test_post_backtest_runs_persists_and_returns_summary(tmp_path: Path) -> None:
    response = build_client(tmp_path).post(
        "/api/research/backtests",
        json=payload("api-run-1"),
    )

    assert response.status_code == 201
    assert response.json() == {
        "contract_version": "research_backtest_api.v1",
        "run_id": "api-run-1",
        "status": "completed",
        "instance_id": "instance-1",
        "realised_trade_count": 1,
        "open_position_count": 0,
        "final_equity": "1009.59000",
        "net_pnl": "9.59000",
        "artifact_path": str(tmp_path / "api-run-1"),
        "manifest_contract_version": "research_run_artifacts.v1",
        "market_data_hash": "market-hash",
    }
    assert (tmp_path / "api-run-1" / "manifest.json").is_file()
    assert (tmp_path / "api-run-1" / "result.json").is_file()


def test_existing_run_id_returns_stable_conflict(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    first = client.post("/api/research/backtests", json=payload("duplicate-run"))
    second = client.post("/api/research/backtests", json=payload("duplicate-run"))

    assert first.status_code == 201
    assert second.status_code == 409
    body = second.json()
    assert body["error"] == "run_already_exists"
    assert body["details"] == {"run_id": "duplicate-run"}


def test_backtest_api_is_declared_once_in_openapi(tmp_path: Path) -> None:
    paths = build_client(tmp_path).get("/openapi.json").json()["paths"]
    operation = paths["/api/research/backtests"]["post"]

    assert operation["responses"]["201"]["description"] == "Successful Response"
