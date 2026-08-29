from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.application.backtests import (
    PersistSingleInstanceRun,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import ExplicitRange
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    INSTANCE_ID,
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_projection,
)


def diagnostic_strategy_projection():
    """`strategy_projection()` plus a `StrategyDiagnosticEvaluationDTO`-
    shaped dense fixture, returned as a tuple -- the projection drives
    execution (via `evaluate_range_projection`), the diagnostic payload
    drives `evaluate_range_diagnostics` (a genuinely separate Engine
    call, per `research-diagnostics-projection-v1`)."""

    projection = strategy_projection()
    direction = {
        "side": "long",
        "direction": {
            "component_id": "ema_anchor_stack_trend",
            "instance_id": "ema_anchor_stack_trend",
            "allowed": [True, True, False],
        },
        "blockers": [],
        "blockers_ok": [True, True, True],
        "pre_setup_allowed": [True, True, False],
    }
    setup = {
        "side": "long",
        "setups": [
            {
                "component_id": "untouched_anchor_setup",
                "instance_id": "setup-1",
                "allowed": [True, True, False],
            }
        ],
        "setups_ok": [True, True, False],
        "pre_trigger_allowed": [True, True, False],
    }
    trigger = {
        "side": "long",
        "trigger": {
            "component_id": "touch_anchor",
            "allowed": [True, False, False],
        },
        "pre_risk_entry_allowed": [True, False, False],
    }
    risk = {
        "side": "long",
        "risk": {"component_id": "no_risk_filter", "allowed": [True, True, True]},
        "entry_allowed": [True, False, False],
    }
    diagnostics_payload = {
        "contract_version": "strategy_diagnostic_evaluation.v1",
        "strategy_id": projection.strategy_id,
        "config_hash": projection.config_hash,
        "market": projection.market,
        "market_data_hash": projection.market_data_hash,
        "bar_count": projection.bar_count,
        "features": {"series": {}, "mappings": {}},
        "contexts": {},
        "potential_entries": {},
        "component_evidence": {
            "direction_blockers": [direction],
            "setups": [setup],
            "triggers": [trigger],
            "risk_entries": [risk],
            "context_consumption": [],
        },
        "warnings": (),
    }
    return projection, diagnostics_payload


def client_with_run(tmp_path: Path, *, generate_diagnostics: bool = True) -> tuple[TestClient, str]:
    from research_service.domain.contracts import StrategyDiagnosticEvaluationDTO

    projection, diagnostics_payload = diagnostic_strategy_projection()

    class Engine(FakeStrategyEngine):
        def evaluate_range_diagnostics(self, request):
            self.diagnostics_requests = getattr(self, "diagnostics_requests", [])
            self.diagnostics_requests.append(request)
            return StrategyDiagnosticEvaluationDTO.model_validate(diagnostics_payload)

    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    container = Container(
        settings=settings,
        strategy_engine=Engine(projection),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path),
    )
    request = SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        managed_policy_enabled=False,
    )
    outcome = RunSingleInstanceBacktest(
        container.strategy_engine,
        container.market_data,
    ).execute(request)
    PersistSingleInstanceRun(container.artifacts).execute(
        request,
        run_id=outcome.run_id,
        instance_id=outcome.instance_id,
        strategy_evaluation=outcome.strategy_evaluation,
        execution=outcome.execution,
        accounting=outcome.accounting,
        managed_policy_events=outcome.managed_policy_events,
    )
    client = TestClient(create_app(settings, container))
    if generate_diagnostics:
        response = client.post(f"/api/research/runs/{outcome.run_id}/diagnostics/generate")
        assert response.status_code == 200, response.json()
    return client, outcome.run_id


def test_diagnostics_not_yet_generated_before_explicit_generation(tmp_path: Path) -> None:
    client, run_id = client_with_run(tmp_path, generate_diagnostics=False)
    response = client.get(
        f"/api/research/runs/{run_id}/signal-trace",
        params={"instance_id": INSTANCE_ID, "from": 0, "to": 900_000},
    )
    assert response.status_code == 404
    assert response.json()["error"] == "diagnostics_not_yet_generated"


def test_signal_trace_projects_strategy_evidence_and_execution_events(tmp_path: Path) -> None:
    client, run_id = client_with_run(tmp_path)
    response = client.get(
        f"/api/research/runs/{run_id}/signal-trace",
        params={"instance_id": INSTANCE_ID, "from": 0, "to": 900_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "research_signal_trace.v1"
    assert body["times"] == [0, 300, 600]
    assert body["long"]["direction_ok"] == [True, True, False]
    # signal_entry/stop_ready/portfolio_entry collapse to the same series
    # post-I7 (Master Plan invariant: stop_ready does not survive as a
    # standalone entity) -- the fixture's single long entry_opportunity is
    # at bar 0 only.
    assert body["long"]["signal_entry"] == [True, False, False]
    assert body["long"]["portfolio_entry"] == [True, False, False]
    assert body["meta"]["instance_id"] == INSTANCE_ID
    # meta is sourced from the run's own persisted request.strategy.raw_spec
    # (_RAW_SPEC = {"anchor": {"period": 200}}, no declared trigger) -- the
    # default fallback applies, not the diagnostic fixture's own raw_spec
    # (which is never echoed back by Engine's diagnostic contract).
    assert body["meta"]["component_ids"]["trigger"] == "reclaim_anchor"
    execution = [event for event in body["component_events"] if event["role"] == "execution"]
    assert [event["component_id"] for event in execution] == ["entry_filled", "exit_filled"]
    assert any(event["component_id"] == "touch_anchor" for event in body["component_events"])


def test_chart_events_is_sparse_projection_with_coverage(tmp_path: Path) -> None:
    client, run_id = client_with_run(tmp_path)
    response = client.get(
        f"/api/research/runs/{run_id}/chart-events",
        params={"instance_id": INSTANCE_ID, "from": 0, "to": 600_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "research_chart_events.v1"
    assert body["times"] == [0, 300]
    assert body["coverage"]["bar_count"] == 2
    assert body["coverage"]["requested_from_sec"] == 0
    assert body["coverage"]["requested_to_sec"] == 599
    assert any(event["component_id"] == "entry_filled" for event in body["component_events"])


def test_diagnostics_rejects_wrong_instance_id_and_missing_window(tmp_path: Path) -> None:
    client, run_id = client_with_run(tmp_path)
    wrong = client.get(
        f"/api/research/runs/{run_id}/signal-trace",
        params={"instance_id": "other", "from": 0, "to": 900_000},
    )
    missing = client.get(
        f"/api/research/runs/{run_id}/chart-events",
        params={"instance_id": INSTANCE_ID, "from": 0},
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_request"
    assert missing.status_code == 400
    assert missing.json()["error"] == "invalid_request"


def test_legacy_variant_query_param_is_no_longer_supported(tmp_path: Path) -> None:
    # Clean break (research-backtest-api-v1): `variant` was the old wire
    # name for this diagnostics identity; `instance_id` is required and
    # `variant` is not a recognized alias -- omitting the required param
    # fails FastAPI's own request validation (422), before any use case
    # runs.
    client, run_id = client_with_run(tmp_path)
    signal_trace = client.get(
        f"/api/research/runs/{run_id}/signal-trace",
        params={"variant": INSTANCE_ID, "from": 0, "to": 900_000},
    )
    chart_events = client.get(
        f"/api/research/runs/{run_id}/chart-events",
        params={"variant": INSTANCE_ID, "from": 0, "to": 900_000},
    )
    assert signal_trace.status_code == 422
    assert chart_events.status_code == 422
