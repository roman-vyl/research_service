"""Chart-events endpoint tests (Phase 4)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from research_api.contracts.chart_events import cached_chart_events_key
from research_api.contracts.signal_trace import (
    ComponentEvent,
    HtfContextTrace,
    SignalTraceBundle,
    SignalTraceMeta,
    SideSignalTrace,
)
from research_api.main import app
from research_api.services import chart_events_service as ces

pytestmark = pytest.mark.workbench_api


def _empty_side() -> SideSignalTrace:
    return SideSignalTrace(
        direction_ok=[True, False],
        blockers_ok=[True, True],
        setup_ok=[False, True],
        trigger_ok=[True, True],
        risk_ok=[True, True],
        signal_entry=[False, False],
        stop_ready=[True, True],
        portfolio_entry=[False, False],
        internals={"direction": {"ema_slope": [0.1, 0.2]}},
    )


def _sample_trace(*, htf_fast: list[float | None] | None = None) -> SignalTraceBundle:
    meta = SignalTraceMeta(
        variant="v1",
        component_ids={
            "direction": "ema_anchor_stack_trend",
            "setups": [{"instance_id": "setup", "component_id": "untouched_anchor_setup"}],
            "trigger": "reclaim_anchor",
            "risk": "no_risk_filter",
        },
        setup_params=[],
        blocker_instances=[],
    )
    fast = htf_fast if htf_fast is not None else [10.0, 11.0]
    return SignalTraceBundle(
        times=[1_700_000_000, 1_700_000_300],
        meta=meta,
        htf_context=HtfContextTrace(
            state=["up", "neutral"],
            fast=fast,
            anchor=[20.0, 21.0],
            slow=[30.0, 31.0],
            meta={"context_ref": "htf_1", "timeframe": "4h"},
        ),
        context_consumption_trace=[
            {
                "role": "blocker",
                "component_id": "c",
                "context_ref": "htf_1",
                "policy_id": "p",
                "context_applied": [True, False],
            }
        ],
        component_events=[
            ComponentEvent(
                time=1_700_000_000,
                event_type="point",
                role="exit_signal",
                side="long",
                component_id="comp",
                instance_id="inst",
                label="exit",
            )
        ],
        long=_empty_side(),
        short=_empty_side(),
    )


def test_chart_events_endpoint_returns_sparse_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "research_api.routers.research_runs.fetch_chart_events_bundle",
        lambda **_kwargs: ces._project_display_bundle(
            _sample_trace(),
            requested_from_sec=1_700_000_000,
            requested_to_sec=1_700_000_300,
        ),
    )

    client = TestClient(app)
    res = client.get(
        "/api/research/runs/run1/chart-events",
        params={"variant": "v1", "from": 0, "to": 1000},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["times"] == [1_700_000_000, 1_700_000_300]
    assert body["component_events"][0]["label"] == "exit"
    assert body["htf_context"]["fast"] == [10.0, 11.0]
    assert "state" not in body["htf_context"]
    assert "long" not in body
    assert "short" not in body
    assert "context_consumption_trace" not in body
    assert body["coverage"]["schema_version"] == 1


def test_chart_events_display_fields_match_signal_trace_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = _sample_trace()
    monkeypatch.setattr(ces, "fetch_signal_trace_bundle", MagicMock(return_value=trace))
    monkeypatch.setattr(
        ces,
        "load_run_report",
        MagicMock(return_value=MagicMock(timeframe="5m")),
    )
    ces._CHART_EVENTS_CACHE.clear()

    bundle = ces.fetch_chart_events_bundle(
        run_id="run1",
        variant_key="v1",
        from_ms=1_700_000_000_000,
        to_open_time_ms=1_700_000_300_000,
    )

    assert bundle.times == trace.times
    assert len(bundle.component_events) == len(trace.component_events)
    assert bundle.component_events[0].time == trace.component_events[0].time
    assert bundle.htf_context.fast == trace.htf_context.fast
    assert bundle.htf_context.anchor == trace.htf_context.anchor
    assert bundle.htf_context.slow == trace.htf_context.slow
    assert bundle.htf_context.meta == trace.htf_context.meta


def test_chart_events_endpoint_cache_hit_calls_trace_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = _sample_trace()
    fetch_mock = MagicMock(return_value=trace)
    monkeypatch.setattr(ces, "fetch_signal_trace_bundle", fetch_mock)
    monkeypatch.setattr(
        ces,
        "load_run_report",
        MagicMock(return_value=MagicMock(timeframe="5m")),
    )
    ces._CHART_EVENTS_CACHE.clear()

    client = TestClient(app)
    params = {
        "variant": "v1",
        "from": 1_700_000_000_000,
        "to_open_time_ms": 1_700_000_300_000,
        "context_overlay_ref": "htf_1",
    }
    first = client.get("/api/research/runs/run1/chart-events", params=params)
    second = client.get("/api/research/runs/run1/chart-events", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert fetch_mock.call_count == 1
    assert first.json()["times"] == second.json()["times"]


def test_chart_events_cache_key_includes_context_overlay_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_empty = _sample_trace(htf_fast=[])
    trace_htf = _sample_trace(htf_fast=[99.0, 100.0])
    fetch_mock = MagicMock(side_effect=[trace_empty, trace_htf])
    monkeypatch.setattr(ces, "fetch_signal_trace_bundle", fetch_mock)
    monkeypatch.setattr(
        ces,
        "load_run_report",
        MagicMock(return_value=MagicMock(timeframe="5m")),
    )
    ces._CHART_EVENTS_CACHE.clear()

    client = TestClient(app)
    base_params = {
        "variant": "v1",
        "from": 1_000,
        "to": 2_000,
    }
    res_a = client.get("/api/research/runs/run1/chart-events", params=base_params)
    res_b = client.get(
        "/api/research/runs/run1/chart-events",
        params={**base_params, "context_overlay_ref": "htf_1"},
    )

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert fetch_mock.call_count == 2
    assert res_a.json()["htf_context"]["fast"] == []
    assert res_b.json()["htf_context"]["fast"] == [99.0, 100.0]

    base_key = cached_chart_events_key(
        run_id="run1",
        variant_key="v1",
        from_ms=1_000,
        exclusive_end_ms=2_000,
        context_overlay_ref=None,
    )
    ref_key = cached_chart_events_key(
        run_id="run1",
        variant_key="v1",
        from_ms=1_000,
        exclusive_end_ms=2_000,
        context_overlay_ref="htf_1",
    )
    assert base_key != ref_key
    assert base_key in ces._CHART_EVENTS_CACHE
    assert ref_key in ces._CHART_EVENTS_CACHE


def test_chart_events_to_and_to_open_time_ms_conflict_matches_signal_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
    from research_api.services import signal_trace_service as sts

    spec = make_ema_pullback_strategy_spec()
    variant = MagicMock(variant="v1", strategy_spec={})
    report = MagicMock(timeframe="5m", family="ema_pullback", variants=[variant])
    load_mock = MagicMock(return_value=report)
    monkeypatch.setattr(ces, "load_run_report", load_mock)
    monkeypatch.setattr(sts, "load_run_report", load_mock)
    monkeypatch.setattr(sts, "strategy_spec_from_report_dict", lambda _: spec)
    ces._CHART_EVENTS_CACHE.clear()

    client = TestClient(app)
    params = {
        "variant": "v1",
        "from": 0,
        "to": 1000,
        "to_open_time_ms": 900,
    }
    chart_res = client.get("/api/research/runs/run1/chart-events", params=params)
    trace_res = client.get("/api/research/runs/run1/signal-trace", params=params)

    assert chart_res.status_code == 422
    assert trace_res.status_code == 422
    assert chart_res.status_code == trace_res.status_code
    assert "to_open_time_ms" in chart_res.json()["detail"].lower()
    assert chart_res.json()["detail"] == trace_res.json()["detail"]
    assert len(ces._CHART_EVENTS_CACHE) == 0


def test_chart_events_missing_window_end_returns_400() -> None:
    client = TestClient(app)
    res = client.get(
        "/api/research/runs/run1/chart-events",
        params={"variant": "v1", "from": 0},
    )
    assert res.status_code == 400
    assert "to_open_time_ms" in res.json()["detail"].lower()
