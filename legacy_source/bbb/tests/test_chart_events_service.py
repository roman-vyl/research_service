"""Chart-events service: projection and cache-on-demand (Phase 3 — no router)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from research_api.contracts.chart_events import (
    CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
    cached_chart_events_key,
)
from research_api.contracts.signal_trace import (
    ComponentEvent,
    HtfContextTrace,
    SignalTraceBundle,
    SignalTraceMeta,
    SideSignalTrace,
)
from research_api.services import chart_events_service as ces

pytestmark = pytest.mark.workbench_api


def _empty_side() -> SideSignalTrace:
    return SideSignalTrace(
        direction_ok=[],
        blockers_ok=[],
        setup_ok=[],
        trigger_ok=[],
        risk_ok=[],
        signal_entry=[],
        stop_ready=[],
        portfolio_entry=[],
        internals={},
    )


def _sample_trace(*, times: list[int] | None = None) -> SignalTraceBundle:
    t = times if times is not None else [1_700_000_000, 1_700_000_300]
    meta = SignalTraceMeta(
        variant="v1",
        component_ids={
            "direction": "ema_anchor_stack_trend",
            "setups": [],
            "trigger": "reclaim_trigger",
            "risk": "fixed_risk",
        },
        setup_params=[],
        blocker_instances=[],
    )
    return SignalTraceBundle(
        times=t,
        meta=meta,
        htf_context=HtfContextTrace(
            state=["up", "down"],
            fast=[1.0, 2.0],
            anchor=[3.0, 4.0],
            slow=[5.0, 6.0],
            meta={"context_ref": "htf_1"},
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
                time=t[0],
                event_type="point",
                role="exit_signal",
                side="long",
                component_id="comp",
                instance_id="inst",
                label="x",
            )
        ],
        long=_empty_side(),
        short=_empty_side(),
    )


def test_project_display_bundle_excludes_dense_fields() -> None:
    bundle = ces._project_display_bundle(
        _sample_trace(),
        requested_from_sec=1_700_000_000,
        requested_to_sec=1_700_000_300,
    )
    payload = bundle.model_dump(mode="json")
    assert "long" not in payload
    assert "short" not in payload
    assert "context_consumption_trace" not in payload
    assert "state" not in payload["htf_context"]
    assert bundle.htf_context.fast == [1.0, 2.0]
    assert bundle.component_events[0].label == "x"
    assert bundle.coverage.schema_version == CHART_EVENTS_BUNDLE_SCHEMA_VERSION
    assert bundle.coverage.truncated is False


def test_project_display_bundle_marks_truncated_window() -> None:
    bundle = ces._project_display_bundle(
        _sample_trace(times=[1_700_000_100, 1_700_000_200]),
        requested_from_sec=1_700_000_000,
        requested_to_sec=1_700_000_300,
    )
    assert bundle.coverage.truncated is True


def test_fetch_chart_events_bundle_cache_hit_calls_trace_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ces._CHART_EVENTS_CACHE.clear()
    trace = _sample_trace()
    fetch_mock = MagicMock(return_value=trace)
    monkeypatch.setattr(ces, "load_run_report", MagicMock(return_value=MagicMock(timeframe="5m")))
    monkeypatch.setattr(ces, "fetch_signal_trace_bundle", fetch_mock)
    monkeypatch.setattr(
        ces,
        "resolve_exclusive_to_ms",
        lambda **_kwargs: 1_700_000_600_000,
    )
    monkeypatch.setattr(
        ces,
        "parse_time_range_ms",
        lambda **_kwargs: (1_700_000_000_000, 1_700_000_600_000),
    )

    params = {
        "run_id": "run-1",
        "variant_key": "v1",
        "from_ms": 1_700_000_000_000,
        "to_open_time_ms": 1_700_000_300_000,
        "context_overlay_ref": "htf_1",
    }
    first = ces.fetch_chart_events_bundle(**params)
    second = ces.fetch_chart_events_bundle(**params)

    assert fetch_mock.call_count == 1
    assert first.times == second.times
    assert first.htf_context.fast == second.htf_context.fast
    expected_key = cached_chart_events_key(
        run_id="run-1",
        variant_key="v1",
        from_ms=1_700_000_000_000,
        exclusive_end_ms=1_700_000_600_000,
        context_overlay_ref="htf_1",
    )
    assert expected_key in ces._CHART_EVENTS_CACHE


def test_chart_events_cache_populated_after_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    ces._CHART_EVENTS_CACHE.clear()
    trace = _sample_trace()
    monkeypatch.setattr(ces, "load_run_report", MagicMock(return_value=MagicMock(timeframe="5m")))
    monkeypatch.setattr(ces, "fetch_signal_trace_bundle", MagicMock(return_value=trace))
    monkeypatch.setattr(ces, "resolve_exclusive_to_ms", lambda **_kwargs: 2_000)
    monkeypatch.setattr(ces, "parse_time_range_ms", lambda **_kwargs: (1_000, 2_000))

    ces.fetch_chart_events_bundle(
        run_id="r",
        variant_key="v",
        from_ms=1_000,
        to_ms=2_000,
    )
    assert len(ces._CHART_EVENTS_CACHE) == 1


def _large_signal_trace(*, bar_count: int) -> SignalTraceBundle:
    times = [1_700_000_000 + i * 300 for i in range(bar_count)]
    bool_lane = [i % 2 == 0 for i in range(bar_count)]
    internals = {
        "direction": {"ema_slope": [0.1 if i % 3 == 0 else -0.1 for i in range(bar_count)]},
    }
    side = SideSignalTrace(
        direction_ok=bool_lane,
        blockers_ok=bool_lane,
        setup_ok=bool_lane,
        trigger_ok=bool_lane,
        risk_ok=bool_lane,
        signal_entry=bool_lane,
        stop_ready=bool_lane,
        portfolio_entry=bool_lane,
        internals=internals,
    )
    meta = SignalTraceMeta(
        variant="v1",
        component_ids={
            "direction": "ema_anchor_stack_trend",
            "setups": [],
            "trigger": "reclaim_trigger",
            "risk": "fixed_risk",
        },
        setup_params=[],
        blocker_instances=[],
    )
    return SignalTraceBundle(
        times=times,
        meta=meta,
        htf_context=HtfContextTrace(
            state=["up" if i % 2 == 0 else "neutral" for i in range(bar_count)],
            fast=[float(i) for i in range(bar_count)],
            anchor=[float(i) + 0.5 for i in range(bar_count)],
            slow=[float(i) + 1.0 for i in range(bar_count)],
            meta={"context_ref": "htf_1", "timeframe": "4h"},
        ),
        context_consumption_trace=[
            {
                "role": "blocker",
                "component_id": "c",
                "context_ref": "htf_1",
                "policy_id": "p",
                "context_applied": bool_lane,
            }
        ],
        component_events=[
            ComponentEvent(
                time=times[i],
                event_type="point",
                role="exit_signal",
                side="long",
                component_id="comp",
                instance_id="inst",
                label=f"exit-{i}",
            )
            for i in range(0, bar_count, max(1, bar_count // 50))
        ],
        long=side,
        short=side,
    )


def test_chart_events_payload_ratio_at_representative_window() -> None:
    """Phase 6.1: sparse chart-events JSON is materially smaller than dense signal-trace."""
    bar_count = 50_000
    trace = _large_signal_trace(bar_count=bar_count)
    sparse = ces._project_display_bundle(
        trace,
        requested_from_sec=trace.times[0],
        requested_to_sec=trace.times[-1],
    )

    dense_bytes = len(json.dumps(trace.model_dump(mode="json")).encode("utf-8"))
    sparse_bytes = len(json.dumps(sparse.model_dump(mode="json")).encode("utf-8"))
    ratio = dense_bytes / sparse_bytes

    assert sparse_bytes < dense_bytes
    assert ratio >= 3.0
