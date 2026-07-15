from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.api.app import create_app
from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_request,
    strategy_result,
)


def diagnostic_strategy_result():
    base = strategy_result()
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
    raw = {
        "strategy": {
            "raw_spec": {
                "components": {
                    "direction": "ema_anchor_stack_trend",
                    "setups": [
                        {"component_id": "untouched_anchor_setup", "instance_id": "setup-1"}
                    ],
                    "trigger": {"component_id": "touch_anchor", "lookback": 1},
                    "risk": "no_risk_filter",
                    "blockers": [],
                }
            }
        },
        "features": {"series": {}, "mappings": {}},
        "contexts": {},
    }
    return base.model_copy(
        update={
            "component_evidence": {
                "direction_blockers": [direction],
                "setups": [setup],
                "triggers": [trigger],
                "risk_entries": [risk],
                "context_consumption": [],
            },
            "raw": raw,
        }
    )


def client_with_run(tmp_path: Path) -> TestClient:
    settings = Settings(artifacts_root=tmp_path)
    result_fixture = diagnostic_strategy_result()
    container = Container(
        settings=settings,
        strategy_engine=FakeStrategyEngine(result_fixture),
        market_data=FakeMarketData(market_frame()),
        artifacts=FilesystemArtifactStore(tmp_path),
    )
    request = SingleInstanceBacktestRequest(
        run_id="diag-run",
        strategy=strategy_request(),
        managed_policy_enabled=False,
    )
    result = RunSingleInstanceBacktest(
        container.strategy_engine,
        container.market_data,
    ).execute(request)
    PersistSingleInstanceBacktest(container.artifacts).execute(request, result)
    return TestClient(create_app(settings, container))


def test_signal_trace_projects_strategy_evidence_and_execution_events(tmp_path: Path) -> None:
    response = client_with_run(tmp_path).get(
        "/api/research/runs/diag-run/signal-trace",
        params={"variant": "instance-1", "from": 0, "to": 900_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "research_signal_trace.v1"
    assert body["times"] == [0, 300, 600]
    assert body["long"]["direction_ok"] == [True, True, False]
    assert body["long"]["signal_entry"] == [True, False, False]
    assert body["long"]["portfolio_entry"] == [True, False, False]
    assert body["meta"]["component_ids"]["trigger"] == "touch_anchor"
    execution = [event for event in body["component_events"] if event["role"] == "execution"]
    assert [event["component_id"] for event in execution] == ["entry_filled", "exit_filled"]
    assert any(event["component_id"] == "touch_anchor" for event in body["component_events"])


def test_chart_events_is_sparse_projection_with_coverage(tmp_path: Path) -> None:
    response = client_with_run(tmp_path).get(
        "/api/research/runs/diag-run/chart-events",
        params={"variant": "instance-1", "from": 0, "to": 600_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "research_chart_events.v1"
    assert body["times"] == [0, 300]
    assert body["coverage"]["bar_count"] == 2
    assert body["coverage"]["requested_from_sec"] == 0
    assert body["coverage"]["requested_to_sec"] == 599
    assert any(event["component_id"] == "entry_filled" for event in body["component_events"])


def test_diagnostics_rejects_wrong_variant_and_missing_window(tmp_path: Path) -> None:
    client = client_with_run(tmp_path)
    wrong = client.get(
        "/api/research/runs/diag-run/signal-trace",
        params={"variant": "other", "from": 0, "to": 900_000},
    )
    missing = client.get(
        "/api/research/runs/diag-run/chart-events",
        params={"variant": "instance-1", "from": 0},
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_request"
    assert missing.status_code == 400
    assert missing.json()["error"] == "invalid_request"
