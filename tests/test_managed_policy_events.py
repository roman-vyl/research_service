from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.application.backtests import (
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (
    ExplicitRange,
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.managed_policy_events import capture_managed_policy_events
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_result,
)


class ManagedEventsStrategyEngine(FakeStrategyEngine):
    """FakeStrategyEngine whose managed replay carries real Engine-shaped events."""

    def evaluate_managed_replay(self, request: ManagedReplayRequest) -> ManagedReplayResult:
        self.managed_requests.append(request)
        return ManagedReplayResult(
            contract_version="managed_policy_replay.v1",
            decision_timing="end_of_bar_effective_next_bar",
            trade_id=request.trade_id,
            side=request.side,
            entry_time_ms=request.entry_time_ms,
            bars=(
                ManagedBarDecision(
                    time_ms=0,
                    bar_index=0,
                    phase="initial_risk",
                    bars_in_trade=1,
                    mfe_pct=Decimal("0.02"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=None,
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=300_000,
                ),
                ManagedBarDecision(
                    time_ms=300_000,
                    bar_index=1,
                    phase="proven",
                    bars_in_trade=2,
                    mfe_pct=Decimal("0.06"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=Decimal("99.75"),
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=None,
                ),
            ),
            events=(
                {
                    "time_ms": 0,
                    "bar_index": 0,
                    "event_type": "phase_changed",
                    "rule_id": "phase-rule-1",
                    "component_id": "phase-component",
                    "from_phase": "initial_risk",
                    "to_phase": "proven",
                    "price": "100.5",
                    "metadata": {"note": "proven"},
                },
                {
                    "time_ms": 0,
                    "bar_index": 0,
                    "event_type": "active_stop_updated",
                    "rule_id": "stop-rule-1",
                    "component_id": "break_even_stop",
                    "from_phase": None,
                    "to_phase": None,
                    "price": "99.75",
                    "metadata": {"effective_from_bar": 1},
                },
            ),
            final_state={},
            raw={},
        )


def _request(*, managed_policy_enabled: bool) -> SingleInstanceBacktestRequest:
    return SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=managed_policy_enabled,
    )


def test_managed_replay_events_survive_execution_loop() -> None:
    """1. Engine managed replay events are captured before the loop discards the timeline,
    and returned as part of the one authoritative execute() outcome — not a caller-owned
    sink."""

    engine = ManagedEventsStrategyEngine(strategy_result())
    use_case = RunSingleInstanceBacktest(engine, FakeMarketData(market_frame()))

    outcome = use_case.execute(_request(managed_policy_enabled=True))

    assert len(outcome.result.accounting.trades) == 1
    position_id = outcome.result.accounting.trades[0].position_id
    assert len(outcome.managed_policy_events) == 2
    assert {event.event_type for event in outcome.managed_policy_events} == {
        "phase_changed",
        "active_stop_updated",
    }
    assert all(event.position_id == position_id for event in outcome.managed_policy_events)
    assert all(event.side == "long" for event in outcome.managed_policy_events)


def test_capture_managed_policy_events_attributes_wrapper_fields() -> None:
    """Unit-level: position_id/side come from the caller, not reconstructed from Engine wire data."""

    replay = ManagedReplayResult(
        contract_version="managed_policy_replay.v1",
        decision_timing="end_of_bar_effective_next_bar",
        trade_id="ignored-on-purpose",
        side="short",
        entry_time_ms=0,
        bars=(),
        events=(
            {
                "time_ms": 300_000,
                "bar_index": 1,
                "event_type": "runtime_exit_triggered",
                "rule_id": "runtime-1",
                "component_id": "runtime-component",
                "from_phase": None,
                "to_phase": None,
                "price": "104.0",
                "metadata": {"exit_kind": "market_close"},
            },
        ),
        final_state={},
        raw={},
    )

    records = capture_managed_policy_events(replay, position_id="position-xyz", side="long")

    assert len(records) == 1
    record = records[0]
    assert record.position_id == "position-xyz"
    assert record.side == "long"
    assert record.event_type == "runtime_exit_triggered"
    assert record.price == Decimal("104.0")
    assert record.metadata == {"exit_kind": "market_close"}


def _container(tmp_path: Path, engine: Any) -> Container:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return Container(
        settings=settings,
        strategy_engine=engine,
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path),
    )


def _persist_via_backtest_endpoint(
    tmp_path: Path,
    *,
    managed_policy_enabled: bool,
) -> tuple[TestClient, str]:
    engine = ManagedEventsStrategyEngine(strategy_result())
    container = _container(tmp_path, engine)
    client = TestClient(create_app(container.settings, container))
    payload = _request(managed_policy_enabled=managed_policy_enabled)
    response = client.post("/api/research/backtests", json=json.loads(payload.model_dump_json()))
    assert response.status_code == 201, response.json()
    return client, response.json()["run_id"]


def test_artifact_is_published_and_hash_verified_via_manifest(tmp_path: Path) -> None:
    """2. Artifact publishes with the run and is hash-verified through the existing manifest mechanism."""

    _client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=True)

    run_dir = tmp_path / run_id
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    record = next(f for f in manifest["files"] if f["path"] == "managed_policy_events.json")
    payload = (run_dir / "managed_policy_events.json").read_bytes()

    import hashlib

    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert record["size_bytes"] == len(payload)

    trace = json.loads(payload)
    assert trace["contract_version"] == "research_managed_policy_events.v1"
    assert trace["run_id"] == run_id
    assert len(trace["events"]) == 2


def test_api_returns_events_for_correct_run_and_trade(tmp_path: Path) -> None:
    """3 + 4. API returns the right run/trade's events, correlated via position_id."""

    client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=True)

    trades = client.get(f"/api/research/runs/{run_id}/trades").json()["trades"]
    assert len(trades) == 1
    position_id = trades[0]["position_id"]
    trade_id = trades[0]["trade_id"]
    assert trade_id != position_id  # trade_id is derived ("trade:{position_id}:{ordinal}")

    full = client.get(f"/api/research/runs/{run_id}/managed-policy-events")
    assert full.status_code == 200
    assert full.json()["contract_version"] == "research_managed_policy_events.v1"
    assert full.json()["run_id"] == run_id
    assert len(full.json()["events"]) == 2
    assert all(event["position_id"] == position_id for event in full.json()["events"])

    scoped = client.get(
        f"/api/research/runs/{run_id}/managed-policy-events",
        params={"position_id": position_id},
    )
    assert scoped.status_code == 200
    assert len(scoped.json()["events"]) == 2

    # Filtering by the derived trade_id (not position_id) must not accidentally match.
    wrong_key = client.get(
        f"/api/research/runs/{run_id}/managed-policy-events",
        params={"position_id": trade_id},
    )
    assert wrong_key.status_code == 400
    assert wrong_key.json()["error"] == "invalid_request"


def test_run_without_managed_policy_returns_empty_trace(tmp_path: Path) -> None:
    """5. A run with managed policy disabled returns a valid empty trace, not an error."""

    client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=False)

    response = client.get(f"/api/research/runs/{run_id}/managed-policy-events")

    assert response.status_code == 200
    assert response.json()["events"] == []


def test_invalid_run_and_trade_fail_closed(tmp_path: Path) -> None:
    """6. Unknown run -> 404 run_not_found; unknown trade in a known run -> 400 invalid_request."""

    client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=True)

    missing_run = client.get("/api/research/runs/does-not-exist/managed-policy-events")
    assert missing_run.status_code == 404
    assert missing_run.json()["error"] == "run_not_found"

    unknown_trade = client.get(
        f"/api/research/runs/{run_id}/managed-policy-events",
        params={"position_id": "position-does-not-exist"},
    )
    assert unknown_trade.status_code == 400
    assert unknown_trade.json()["error"] == "invalid_request"


def test_existing_run_projections_are_unaffected(tmp_path: Path) -> None:
    """7. detail/trades/metrics contracts stay exactly as before this change."""

    client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=True)

    detail = client.get(f"/api/research/runs/{run_id}").json()
    assert set(detail.keys()) == {"contract_version", "manifest", "result", "strategy_spec"}

    trades = client.get(f"/api/research/runs/{run_id}/trades").json()
    assert trades["contract_version"] == "research_run_trades.v1"

    metrics = client.get(f"/api/research/runs/{run_id}/metrics").json()
    assert metrics["contract_version"] == "research_run_metrics.v1"


def test_legacy_bundle_without_managed_policy_events_file_stays_readable(tmp_path: Path) -> None:
    """8. A bundle written before this projection existed (no managed_policy_events.json
    on disk, and no record of it in manifest.json) must not become fully unreadable.
    detail/trades/metrics stay servable; the managed-policy-events endpoint must say
    "trace unavailable for this legacy artifact", not silently claim an empty trace."""

    client, run_id = _persist_via_backtest_endpoint(tmp_path, managed_policy_enabled=True)

    run_dir = tmp_path / run_id
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [
        f for f in manifest["files"] if f["path"] != "managed_policy_events.json"
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "managed_policy_events.json").unlink()

    detail = client.get(f"/api/research/runs/{run_id}")
    assert detail.status_code == 200

    trades = client.get(f"/api/research/runs/{run_id}/trades")
    assert trades.status_code == 200

    metrics = client.get(f"/api/research/runs/{run_id}/metrics")
    assert metrics.status_code == 200

    trace = client.get(f"/api/research/runs/{run_id}/managed-policy-events")
    assert trace.status_code == 404
    assert trace.json()["error"] == "managed_policy_trace_unavailable"
