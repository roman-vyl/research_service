from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.api.contracts.backtests import BacktestRunRequest
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import DeployableStrategyInstance
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    INSTANCE_ID,
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_projection,
)

_RAW_SPEC = {"anchor": {"period": 200}}


def deployable_instance(**overrides: object) -> DeployableStrategyInstance:
    payload: dict[str, object] = {
        "enabled": True,
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": _RAW_SPEC,
    }
    payload.update(overrides)
    return DeployableStrategyInstance(**payload)  # type: ignore[arg-type]


def build_client(tmp_path: Path) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(
                settings=settings,
                strategy_engine=FakeStrategyEngine(strategy_projection()),
                market_data=FakeMarketData(market_frame()),
                artifacts=FilesystemArtifactStore(tmp_path),
            ),
        )
    )


def payload() -> dict[str, object]:
    request = BacktestRunRequest(
        strategy=deployable_instance(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
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
        json=payload(),
    )

    assert response.status_code == 201
    body = response.json()
    run_id = body["run_id"]
    assert run_id
    assert body == {
        "contract_version": "research_backtest_api.v1",
        "run_id": run_id,
        "status": "completed",
        "instance_id": INSTANCE_ID,
        "realised_trade_count": 1,
        "open_position_count": 0,
        "final_equity": "1009.59000",
        "net_pnl": "9.59000",
        "artifact_path": str(tmp_path / run_id),
        "manifest_contract_version": "research_run_artifacts.v1",
        "market_data_hash": "market-hash",
    }
    assert (tmp_path / run_id / "manifest.json").is_file()
    assert (tmp_path / run_id / "result.json").is_file()


def test_two_identical_requests_create_two_distinct_runs(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    first = client.post("/api/research/backtests", json=payload())
    second = client.post("/api/research/backtests", json=payload())

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["run_id"] != second.json()["run_id"]


def test_run_id_is_rejected_as_a_request_field(tmp_path: Path) -> None:
    body = payload()
    body["run_id"] = "caller-supplied"

    response = build_client(tmp_path).post("/api/research/backtests", json=body)

    assert response.status_code == 422


def test_explicit_range_without_range_is_rejected(tmp_path: Path) -> None:
    body = payload()
    body["range_policy"] = "explicit_range"
    body["range"] = None

    response = build_client(tmp_path).post("/api/research/backtests", json=body)

    assert response.status_code == 422


def test_full_available_with_range_is_rejected(tmp_path: Path) -> None:
    body = payload()
    body["range_policy"] = "full_available"
    # `range` stays populated from payload() — full_available must not
    # accept it, not even a well-formed one.

    response = build_client(tmp_path).post("/api/research/backtests", json=body)

    assert response.status_code == 422


def test_legacy_identity_fields_are_rejected_on_backtest_request(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    for field, value in [
        ("family", "ema_pullback"),
        ("variant", "exp_a"),
        ("strategy_version", "v1"),
        ("instance_id", "caller-chosen"),
        ("market", {"symbol": "BTCUSDT", "base_timeframe": "5m"}),
        ("strategy", {"trade_sides": ["long"]}),
    ]:
        body = payload()
        body["strategy"][field] = value
        response = client.post("/api/research/backtests", json=body)
        assert response.status_code == 422, f"expected rejection for strategy.{field}"


def test_enabled_field_is_accepted_on_backtest_request(tmp_path: Path) -> None:
    # enabled is deployment metadata, not a legacy field -- it MUST be
    # accepted at this boundary (research-backtest-api-v1, "Public request
    # accepts a canonical deployable instance").
    response = build_client(tmp_path).post("/api/research/backtests", json=payload())
    assert response.status_code == 201


def test_enabled_true_and_false_produce_identical_derived_instance_identity(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    enabled_body = payload()
    disabled_body = payload()
    disabled_body["strategy"]["enabled"] = False

    enabled_response = client.post("/api/research/backtests", json=enabled_body)
    disabled_response = client.post("/api/research/backtests", json=disabled_body)

    assert enabled_response.status_code == disabled_response.status_code == 201
    assert enabled_response.json()["instance_id"] == disabled_response.json()["instance_id"]
    assert enabled_response.json()["instance_id"] == INSTANCE_ID
    # both actually ran and each got its own run
    assert enabled_response.json()["run_id"] != disabled_response.json()["run_id"]


def test_projection_drops_enabled_from_internal_request(tmp_path: Path) -> None:
    # request.json is the persisted internal SingleInstanceBacktestRequest --
    # StrategyInstanceIdentity has no `enabled` field at all, proving the
    # projection actually happened (build_backtest_request semantics), not
    # some other pass-through mapping.
    response = build_client(tmp_path).post("/api/research/backtests", json=payload())
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    persisted_request = json.loads((tmp_path / run_id / "request.json").read_text())
    assert "enabled" not in persisted_request["strategy"]
    assert set(persisted_request["strategy"]) == {"strategy_id", "ticker", "base_timeframe", "raw_spec"}
    assert persisted_request["strategy"]["raw_spec"] == _RAW_SPEC


def test_backtest_api_is_declared_once_in_openapi(tmp_path: Path) -> None:
    paths = build_client(tmp_path).get("/openapi.json").json()["paths"]
    operation = paths["/api/research/backtests"]["post"]

    assert operation["responses"]["201"]["description"] == "Successful Response"
