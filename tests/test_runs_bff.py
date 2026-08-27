from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_result,
)


def _container(tmp_path: Path) -> Container:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(strategy_result()),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path),
    )


def _persist(tmp_path: Path, created_at: str) -> str:
    """Persist one completed backtest and return its generated run_id."""
    request = SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("10.00"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )
    container = _container(tmp_path)
    outcome = RunSingleInstanceBacktest(
        container.strategy_engine,
        container.market_data,
    ).execute(request)
    run_id = outcome.result.run_id
    PersistSingleInstanceBacktest(container.artifacts).execute(
        request, outcome.result, outcome.managed_policy_events
    )
    manifest_path = tmp_path / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["created_at_utc"] = created_at
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return run_id


def _client(tmp_path: Path) -> TestClient:
    container = _container(tmp_path)
    return TestClient(create_app(container.settings, container))


def test_runs_list_and_latest_use_new_artifact_bundles(tmp_path: Path) -> None:
    older_run_id = _persist(tmp_path, "2026-01-01T00:00:00+00:00")
    newer_run_id = _persist(tmp_path, "2026-01-02T00:00:00+00:00")

    client = _client(tmp_path)
    listed = client.get("/api/research/runs")
    latest = client.get("/api/research/runs/latest")

    assert listed.status_code == 200
    assert [item["run_id"] for item in listed.json()] == [newer_run_id, older_run_id]
    assert listed.json()[0]["contract_version"] == "research_run_summary.v1"
    assert listed.json()[0]["ticker"] == "BTCUSDT.P"
    assert latest.status_code == 200
    assert latest.json()["contract_version"] == "research_run_detail.v1"
    assert latest.json()["manifest"]["run_id"] == newer_run_id
    assert latest.json()["result"]["run_id"] == newer_run_id
    assert latest.json()["strategy_spec"] == {"anchor": {"period": 200}}


def test_run_detail_and_summary_project_versioned_artifacts(tmp_path: Path) -> None:
    run_id = _persist(tmp_path, "2026-01-01T00:00:00+00:00")
    client = _client(tmp_path)

    detail = client.get(f"/api/research/runs/{run_id}")
    summary = client.get(f"/api/research/runs/{run_id}/summary")
    trades = client.get(f"/api/research/runs/{run_id}/trades")
    metrics = client.get(f"/api/research/runs/{run_id}/metrics")

    assert detail.status_code == 200
    assert detail.json()["manifest"]["contract_version"] == "research_run_artifacts.v1"
    assert detail.json()["result"]["contract_version"] == "research_single_instance_backtest.v1"
    assert detail.json()["strategy_spec"] == {"anchor": {"period": 200}}
    detail_keys = set(detail.json().keys())
    assert {"contract_version", "manifest", "result", "strategy_spec"} <= detail_keys
    assert detail_keys.isdisjoint(
        {
            "execution",
            "accounting",
            "range_policy",
            "managed_policy_enabled",
            "compatibility_profile",
            "expected_market_data_hash",
            "include_features",
            "include_contexts",
            "include_component_evidence",
        }
    )
    assert summary.status_code == 200
    assert summary.json()["contract_version"] == "research_run_compact_summary.v1"
    assert summary.json()["summary"]["realised_trade_count"] == 1
    assert summary.json()["gross_pnl"] == "10.00"
    assert summary.json()["fees_paid"] == "0.41000"
    assert trades.status_code == 200
    assert trades.json()["contract_version"] == "research_run_trades.v1"
    assert len(trades.json()["trades"]) == 1
    assert metrics.status_code == 200
    assert metrics.json()["contract_version"] == "research_run_metrics.v1"
    assert metrics.json()["net_pnl"] == "9.59000"


def test_missing_and_corrupt_run_have_stable_errors(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing = client.get("/api/research/runs/missing-run")
    assert missing.status_code == 404
    assert missing.json()["error"] == "run_not_found"

    run_id = _persist(tmp_path, "2026-01-01T00:00:00+00:00")
    (tmp_path / run_id / "result.json").write_text("{bad", encoding="utf-8")
    broken = client.get(f"/api/research/runs/{run_id}")
    assert broken.status_code == 500
    assert broken.json()["error"] == "invalid_run_artifact"


def test_valid_json_tampering_is_rejected_by_manifest_hash(tmp_path: Path) -> None:
    run_id = _persist(tmp_path, "2026-01-01T00:00:00+00:00")
    metrics_path = tmp_path / run_id / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["net_pnl"] = "999.00"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    response = _client(tmp_path).get(f"/api/research/runs/{run_id}/metrics")

    assert response.status_code == 500
    assert response.json()["error"] == "invalid_run_artifact"
    assert "mismatch" in response.json()["message"]


def test_summary_reports_resolved_market_not_requested_market(tmp_path: Path) -> None:
    # full_available carries no range at all — only ticker/base_timeframe
    # (from the identity subset) select the stream; the resolved window
    # comes entirely from MDS bounds.
    resolved_market = market_frame().market
    request = SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range_policy="full_available",
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("10.00"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )
    container = Container(
        settings=Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs"),
        strategy_engine=FakeStrategyEngine(strategy_result(market=resolved_market)),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path),
    )
    outcome = RunSingleInstanceBacktest(
        container.strategy_engine,
        container.market_data,
    ).execute(request)
    run_id = outcome.result.run_id
    PersistSingleInstanceBacktest(container.artifacts).execute(
        request, outcome.result, outcome.managed_policy_events
    )

    client = TestClient(create_app(container.settings, container))
    listed = client.get("/api/research/runs")
    summary = client.get(f"/api/research/runs/{run_id}/summary")

    assert listed.json()[0]["from_ms"] == resolved_market.from_ms
    assert listed.json()[0]["to_ms"] == resolved_market.to_ms
    assert summary.json()["summary"]["from_ms"] == resolved_market.from_ms
    assert summary.json()["summary"]["to_ms"] == resolved_market.to_ms


def test_runs_routes_are_declared_once(tmp_path: Path) -> None:
    paths = _client(tmp_path).get("/openapi.json").json()["paths"]
    assert set(path for path in paths if path.startswith("/api/research/runs")) == {
        "/api/research/runs",
        "/api/research/runs/latest",
        "/api/research/runs/{run_id}",
        "/api/research/runs/{run_id}/summary",
        "/api/research/runs/{run_id}/trades",
        "/api/research/runs/{run_id}/metrics",
        "/api/research/runs/{run_id}/signal-trace",
        "/api/research/runs/{run_id}/chart-events",
        "/api/research/runs/{run_id}/managed-policy-events",
    }
