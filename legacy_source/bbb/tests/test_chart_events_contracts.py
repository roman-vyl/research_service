"""Chart-events contract and cache-key tests (Phase 2 — no service/router)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_api.contracts.chart_events import (
    CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
    ChartEventsBundle,
    ChartEventsCoverage,
    ChartEventsHtfContext,
    cached_chart_events_key,
)

pytestmark = pytest.mark.workbench_api


def _minimal_meta() -> dict:
    return {
        "variant": "v1",
        "component_ids": {
            "direction": "ema_anchor_stack_trend",
            "setups": [],
            "trigger": "reclaim_trigger",
            "risk": "fixed_risk",
        },
        "setup_params": [],
        "blocker_instances": [],
    }


def test_chart_events_bundle_serializes_without_dense_fields() -> None:
    bundle = ChartEventsBundle(
        times=[1_700_000_000, 1_700_000_300],
        component_events=[],
        htf_context=ChartEventsHtfContext(fast=[1.0, 2.0], anchor=[3.0, 4.0], slow=[5.0, 6.0], meta={}),
        meta=_minimal_meta(),
        coverage=ChartEventsCoverage(
            schema_version=CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
            from_sec=1_700_000_000,
            to_sec=1_700_000_300,
            bar_count=2,
            requested_from_sec=1_700_000_000,
            requested_to_sec=1_700_000_300,
            truncated=False,
        ),
    )
    payload = bundle.model_dump(mode="json")
    assert "long" not in payload
    assert "short" not in payload
    assert "context_consumption_trace" not in payload
    assert "state" not in payload["htf_context"]
    assert payload["coverage"]["schema_version"] == CHART_EVENTS_BUNDLE_SCHEMA_VERSION


def test_chart_events_htf_context_rejects_state_field() -> None:
    with pytest.raises(ValidationError):
        ChartEventsHtfContext(
            state=["up"],
            fast=[],
            anchor=[],
            slow=[],
            meta={},
        )


def test_chart_events_bundle_rejects_dense_side_fields() -> None:
    with pytest.raises(ValidationError):
        ChartEventsBundle(
            times=[1],
            component_events=[],
            htf_context=ChartEventsHtfContext(fast=[], anchor=[], slow=[], meta={}),
            meta=_minimal_meta(),
            coverage=ChartEventsCoverage(
                from_sec=1,
                to_sec=1,
                bar_count=1,
                requested_from_sec=1,
                requested_to_sec=1,
                truncated=False,
            ),
            long={"direction_ok": [True]},  # type: ignore[call-arg]
        )


def test_cached_chart_events_key_includes_schema_version_and_overlay_ref() -> None:
    base = cached_chart_events_key(
        run_id="run-1",
        variant_key="v1",
        from_ms=1_000,
        exclusive_end_ms=2_000,
    )
    with_ref = cached_chart_events_key(
        run_id="run-1",
        variant_key="v1",
        from_ms=1_000,
        exclusive_end_ms=2_000,
        context_overlay_ref="htf_1",
    )
    assert base.startswith(f"{CHART_EVENTS_BUNDLE_SCHEMA_VERSION}:")
    assert base == f"{CHART_EVENTS_BUNDLE_SCHEMA_VERSION}:run-1:v1:1000:2000:"
    assert with_ref == f"{CHART_EVENTS_BUNDLE_SCHEMA_VERSION}:run-1:v1:1000:2000:htf_1"
    assert base != with_ref


def test_cached_chart_events_key_uses_exclusive_end_not_raw_to_open_time_ms() -> None:
    """Cache key uses parsed exclusive_end_ms (same as signal-trace parsed bounds)."""
    key = cached_chart_events_key(
        run_id="run-1",
        variant_key="v1",
        from_ms=1_700_000_000_000,
        exclusive_end_ms=1_700_029_800_000,
        context_overlay_ref="htf_1",
    )
    assert ":1700029800000:" in key
    assert key.count(":") == 5
