"""Sparse chart display bundle for Workbench Chart (chart-events API)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from research_api.contracts.signal_trace import ComponentEvent, SignalTraceMeta

CHART_EVENTS_BUNDLE_SCHEMA_VERSION = 1
MAX_CHART_EVENTS_BARS = 50_000


class ChartEventsCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(
        default=CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
        description="Matches CHART_EVENTS_BUNDLE_SCHEMA_VERSION and cache key token",
    )
    from_sec: int
    to_sec: int
    bar_count: int
    requested_from_sec: int
    requested_to_sec: int
    truncated: bool
    max_bars: int = MAX_CHART_EVENTS_BARS


class ChartEventsHtfContext(BaseModel):
    """Display-only HTF overlay series — no per-bar regime state."""

    model_config = ConfigDict(extra="forbid")

    fast: list[float | None]
    anchor: list[float | None]
    slow: list[float | None]
    meta: dict[str, Any] = Field(default_factory=dict)


class ChartEventsBundle(BaseModel):
    """Display payload only — no dense lanes or diagnostics trace."""

    model_config = ConfigDict(extra="forbid")

    times: list[int] = Field(description="Unix seconds per bar, aligned with chart candles")
    component_events: list[ComponentEvent] = Field(default_factory=list)
    htf_context: ChartEventsHtfContext = Field(
        default_factory=lambda: ChartEventsHtfContext(fast=[], anchor=[], slow=[], meta={})
    )
    meta: SignalTraceMeta
    coverage: ChartEventsCoverage


def cached_chart_events_key(
    *,
    run_id: str,
    variant_key: str,
    from_ms: int,
    exclusive_end_ms: int,
    context_overlay_ref: str | None = None,
    schema_version: int = CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
) -> str:
    """Deterministic BFF cache key for chart-events (parsed window bounds)."""

    ref_token = context_overlay_ref or ""
    return f"{schema_version}:{run_id}:{variant_key}:{from_ms}:{exclusive_end_ms}:{ref_token}"
