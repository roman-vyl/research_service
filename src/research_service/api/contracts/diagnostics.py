"""Workbench diagnostics contracts projected from immutable run artifacts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SetupComponentRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instance_id: str
    component_id: str


class SignalTraceComponentIds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    direction: str
    setups: tuple[SetupComponentRef, ...] = ()
    trigger: str
    risk: str


class SignalTraceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instance_id: str
    component_ids: SignalTraceComponentIds
    setup_params: tuple[dict[str, Any], ...] = ()
    trigger_params: dict[str, Any] = Field(default_factory=dict)
    blocker_instances: tuple[dict[str, str], ...] = ()


class SideSignalTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    direction_ok: tuple[bool, ...]
    blockers_ok: tuple[bool, ...]
    setup_ok: tuple[bool, ...]
    trigger_ok: tuple[bool, ...]
    risk_ok: tuple[bool, ...]
    signal_entry: tuple[bool, ...]
    stop_ready: tuple[bool, ...]
    portfolio_entry: tuple[bool, ...]
    internals: dict[str, Any] = Field(default_factory=dict)


class ContextConsumptionTraceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str
    component_id: str
    context_ref: str
    policy_id: str
    context_applied: tuple[bool, ...]
    instance_id: str | None = None
    setup_instance_id: str | None = None
    outcome: dict[str, Any] | None = None


class HtfContextTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: tuple[str, ...] = ()
    fast: tuple[float | None, ...] = ()
    anchor: tuple[float | None, ...] = ()
    slow: tuple[float | None, ...] = ()
    meta: dict[str, Any] = Field(default_factory=dict)


class ComponentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    time: int
    event_type: str
    role: str
    side: str
    component_id: str
    instance_id: str
    label: str
    tooltip: str | None = None
    span_id: str | None = None
    feature_family: str | None = None
    source_timeframe: str | None = None
    base_timeframe: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalTraceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["research_signal_trace.v1"] = "research_signal_trace.v1"
    times: tuple[int, ...]
    meta: SignalTraceMeta
    htf_context: HtfContextTrace = HtfContextTrace()
    context_consumption_trace: tuple[ContextConsumptionTraceRecord, ...] = ()
    component_events: tuple[ComponentEvent, ...] = ()
    long: SideSignalTrace
    short: SideSignalTrace


class ChartEventsCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    from_sec: int
    to_sec: int
    bar_count: int
    requested_from_sec: int
    requested_to_sec: int
    truncated: bool
    max_bars: int = 50_000


class ChartEventsBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["research_chart_events.v1"] = "research_chart_events.v1"
    times: tuple[int, ...]
    component_events: tuple[ComponentEvent, ...] = ()
    htf_context: HtfContextTrace = HtfContextTrace()
    meta: SignalTraceMeta
    coverage: ChartEventsCoverage
