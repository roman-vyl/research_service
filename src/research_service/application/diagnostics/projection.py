"""Project Strategy Engine evidence and Research execution events for Workbench."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from research_service.api.contracts.diagnostics import (
    ChartEventsBundle,
    ChartEventsCoverage,
    ComponentEvent,
    ContextConsumptionTraceRecord,
    HtfContextTrace,
    SetupComponentRef,
    SideSignalTrace,
    SignalTraceBundle,
    SignalTraceComponentIds,
    SignalTraceMeta,
)
from research_service.api.contracts.managed_policy_events import ManagedPolicyEventTrace
from research_service.application.backtests.read_artifacts import ReadResearchRuns
from research_service.domain.errors import InvalidRequest

_MAX_BARS = 50_000


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _records(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _bools(value: object, size: int, default: bool = False) -> tuple[bool, ...]:
    if isinstance(value, (list, tuple)) and len(value) == size:
        return tuple(bool(item) for item in value)
    return tuple(default for _ in range(size))


def _find_side(records: Iterable[Mapping[str, Any]], side: str) -> Mapping[str, Any]:
    return next((item for item in records if str(item.get("side")) == side), {})


def _spec_meta(raw_spec: Mapping[str, Any], instance_id: str) -> SignalTraceMeta:
    components = _mapping(raw_spec.get("components"))
    direction_raw = components.get("direction", raw_spec.get("direction", "ema_anchor_stack_trend"))
    direction = str(_mapping(direction_raw).get("component_id", direction_raw))
    trigger_raw = components.get("trigger", raw_spec.get("trigger", "reclaim_anchor"))
    trigger = str(_mapping(trigger_raw).get("component_id", trigger_raw))
    risk_raw = components.get("risk", raw_spec.get("risk", "no_risk_filter"))
    risk = str(_mapping(risk_raw).get("component_id", risk_raw))
    setup_items = components.get("setups", raw_spec.get("setups", []))
    setups: list[SetupComponentRef] = []
    setup_params: list[dict[str, Any]] = []
    for index, item in enumerate(setup_items if isinstance(setup_items, list) else []):
        record = _mapping(item)
        component_id = str(record.get("component_id", "setup"))
        setup_instance = str(record.get("instance_id", f"{component_id}:{index}"))
        setups.append(SetupComponentRef(instance_id=setup_instance, component_id=component_id))
        setup_params.append(dict(record))
    blocker_items = components.get("blockers", raw_spec.get("blockers", []))
    blockers: list[dict[str, str]] = []
    for index, item in enumerate(blocker_items if isinstance(blocker_items, list) else []):
        record = _mapping(item)
        component_id = str(record.get("component_id", "blocker"))
        blockers.append(
            {
                "instance_id": str(record.get("instance_id", f"{component_id}:{index}")),
                "component_id": component_id,
            }
        )
    return SignalTraceMeta(
        instance_id=instance_id,
        component_ids=SignalTraceComponentIds(
            direction=direction,
            setups=tuple(setups),
            trigger=trigger,
            risk=risk,
        ),
        setup_params=tuple(setup_params),
        trigger_params=dict(_mapping(trigger_raw)),
        blocker_instances=tuple(blockers),
    )


def _side_trace(
    evidence: Mapping[str, Any],
    entries: Mapping[str, tuple[bool, ...]],
    exit_policy: Mapping[str, Any],
    side: str,
    size: int,
) -> SideSignalTrace:
    direction = _find_side(_records(evidence.get("direction_blockers")), side)
    setups = _find_side(_records(evidence.get("setups")), side)
    triggers = _find_side(_records(evidence.get("triggers")), side)
    risks = _find_side(_records(evidence.get("risk_entries")), side)
    direction_mask = _mapping(direction.get("direction"))
    trigger_mask = _mapping(triggers.get("trigger"))
    risk_mask = _mapping(risks.get("risk"))
    setup_masks = _records(setups.get("setups"))
    if "setups_ok" in setups:
        setup_ok = _bools(setups.get("setups_ok"), size)
    elif setup_masks:
        setup_ok = tuple(
            all(_bools(item.get("allowed"), size)[i] for item in setup_masks) for i in range(size)
        )
    else:
        setup_ok = tuple(True for _ in range(size))
    signal_entry = tuple(entries.get(side, tuple(False for _ in range(size))))
    stop_ready = _bools(_mapping(exit_policy.get("stop_ready")).get(side), size)
    portfolio_entry = tuple(a and b for a, b in zip(signal_entry, stop_ready, strict=True))
    internals = {
        "direction": dict(direction),
        "setups": dict(setups),
        "trigger": dict(triggers),
        "risk": dict(risks),
    }
    return SideSignalTrace(
        direction_ok=_bools(direction_mask.get("allowed"), size),
        blockers_ok=_bools(direction.get("blockers_ok"), size, default=True),
        setup_ok=setup_ok,
        trigger_ok=_bools(trigger_mask.get("allowed"), size),
        risk_ok=_bools(risk_mask.get("allowed"), size, default=True),
        signal_entry=signal_entry,
        stop_ready=stop_ready,
        portfolio_entry=portfolio_entry,
        internals=internals,
    )


def _context_trace(
    raw: Mapping[str, Any],
    evidence: Mapping[str, Any],
    size: int,
    context_overlay_ref: str | None = None,
) -> tuple[HtfContextTrace, tuple[ContextConsumptionTraceRecord, ...]]:
    contexts = _mapping(raw.get("contexts"))
    items = _mapping(contexts.get("items"))
    first_ref = context_overlay_ref or next(iter(items), None)
    if context_overlay_ref is not None and context_overlay_ref not in items:
        raise InvalidRequest(
            "context_overlay_ref is not defined in the run evaluation",
            {"context_overlay_ref": context_overlay_ref},
        )
    htf = HtfContextTrace()
    if first_ref is not None:
        item = _mapping(items[first_ref])
        provider = _mapping(item.get("provider"))
        features = _mapping(raw.get("features"))
        series = _mapping(features.get("series"))
        mappings = _mapping(features.get("mappings"))
        context_columns = _mapping(_mapping(mappings.get("context_columns")).get(first_ref))

        def series_float(role: str) -> tuple[float | None, ...]:
            values = series.get(context_columns.get(role, ""), [])
            if not isinstance(values, list):
                return tuple(None for _ in range(size))
            return tuple(None if value is None else float(value) for value in values[:size])

        htf = HtfContextTrace(
            state=tuple(str(value) for value in item.get("state", []))[:size],
            fast=series_float("fast"),
            anchor=series_float("anchor"),
            slow=series_float("slow"),
            meta={"context_ref": first_ref, "provider": dict(provider)},
        )
    records: list[ContextConsumptionTraceRecord] = []
    for item in _records(evidence.get("context_consumption")):
        allowed = _bools(item.get("allowed"), size, default=True)
        component_id = str(item.get("component_id") or item.get("role") or "context")
        records.append(
            ContextConsumptionTraceRecord(
                role=str(item.get("role", "context")),
                component_id=component_id,
                context_ref=str(item.get("context_ref", "")),
                policy_id=str(item.get("policy_id", "")),
                context_applied=allowed,
                instance_id=None
                if item.get("instance_id") is None
                else str(item.get("instance_id")),
                setup_instance_id=None,
                outcome={
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "role",
                        "component_id",
                        "context_ref",
                        "policy_id",
                        "allowed",
                        "instance_id",
                    }
                },
            )
        )
    return htf, tuple(records)


def _component_events(result: Any, start: int, end: int) -> tuple[ComponentEvent, ...]:
    events: list[ComponentEvent] = []
    evidence = result.strategy_evaluation.component_evidence
    for group, role in (
        ("direction_blockers", "entry_block"),
        ("setups", "entry_block"),
        ("triggers", "entry_block"),
        ("risk_entries", "entry_block"),
    ):
        for side_record in _records(evidence.get(group)):
            side = str(side_record.get("side", "long"))
            components: list[Mapping[str, Any]] = []
            if group == "direction_blockers":
                components.append(_mapping(side_record.get("direction")))
                components.extend(_records(side_record.get("blockers")))
            elif group == "setups":
                components.extend(_records(side_record.get("setups")))
            elif group == "triggers":
                components.append(_mapping(side_record.get("trigger")))
            else:
                components.append(_mapping(side_record.get("risk")))
            for component in components:
                component_id = str(component.get("component_id", group))
                instance_id = str(component.get("instance_id", component_id))
                allowed = _bools(component.get("allowed"), result.strategy_evaluation.bar_count)
                for index, active in enumerate(allowed):
                    time_ms = result.strategy_evaluation.time_ms[index]
                    if not active or not start <= time_ms < end:
                        continue
                    events.append(
                        ComponentEvent(
                            time=time_ms // 1000,
                            event_type="point",
                            role=role,
                            side=side,
                            component_id=component_id,
                            instance_id=instance_id,
                            label=component_id,
                            base_timeframe=result.strategy_evaluation.market.timeframe,
                            metadata={"evidence_group": group, "bar_index": index},
                        )
                    )
    for event in result.execution.events:
        if not start <= event.time_ms < end:
            continue
        metadata = dict(event.metadata)
        events.append(
            ComponentEvent(
                time=event.time_ms // 1000,
                event_type="point",
                role="execution",
                side=event.side,
                component_id=event.event_type,
                instance_id=event.instance_id,
                label=event.event_type,
                tooltip=str(metadata.get("reason")) if metadata.get("reason") else None,
                base_timeframe=result.strategy_evaluation.market.timeframe,
                metadata={"position_id": event.position_id, "fill_id": event.fill_id, **metadata},
            )
        )
    events.sort(key=lambda item: (item.time, item.role, item.component_id, item.instance_id))
    return tuple(events)


class ProjectRunDiagnostics:
    def __init__(self, runs: ReadResearchRuns) -> None:
        self._runs = runs

    def signal_trace(
        self,
        *,
        run_id: str,
        instance_id: str,
        from_ms: int,
        to_ms: int,
        context_overlay_ref: str | None = None,
    ) -> SignalTraceBundle:
        detail = self._runs.detail(run_id)
        result = detail.result
        if instance_id != result.instance_id:
            raise InvalidRequest(
                "instance_id does not match the single-instance run",
                {"instance_id": instance_id, "run_instance_id": result.instance_id},
            )
        if from_ms >= to_ms:
            raise InvalidRequest("from must be less than to")
        market = result.strategy_evaluation.market
        start = max(from_ms, market.from_ms)
        end = min(to_ms, market.to_ms)
        indices = [
            i for i, value in enumerate(result.strategy_evaluation.time_ms) if start <= value < end
        ]
        if len(indices) > _MAX_BARS:
            indices = indices[:_MAX_BARS]
        times_ms = tuple(result.strategy_evaluation.time_ms[i] for i in indices)
        full_size = result.strategy_evaluation.bar_count
        raw = _mapping(result.strategy_evaluation.raw)
        htf_full, context_full = _context_trace(
            raw, result.strategy_evaluation.component_evidence, full_size, context_overlay_ref
        )

        def sliced_side(side: str) -> SideSignalTrace:
            full = _side_trace(
                result.strategy_evaluation.component_evidence,
                result.strategy_evaluation.entries,
                result.strategy_evaluation.exit_policy,
                side,
                full_size,
            )
            payload = full.model_dump()
            for key in (
                "direction_ok",
                "blockers_ok",
                "setup_ok",
                "trigger_ok",
                "risk_ok",
                "signal_entry",
                "stop_ready",
                "portfolio_entry",
            ):
                values = payload[key]
                payload[key] = tuple(values[i] for i in indices)
            return SideSignalTrace(**payload)

        def sliced(values: tuple[Any, ...]) -> tuple[Any, ...]:
            return tuple(values[i] for i in indices if i < len(values))

        htf = HtfContextTrace(
            state=sliced(htf_full.state),
            fast=sliced(htf_full.fast),
            anchor=sliced(htf_full.anchor),
            slow=sliced(htf_full.slow),
            meta=htf_full.meta,
        )
        contexts = tuple(
            record.model_copy(update={"context_applied": sliced(record.context_applied)})
            for record in context_full
        )
        return SignalTraceBundle(
            times=tuple(value // 1000 for value in times_ms),
            meta=_spec_meta(
                _mapping(result.strategy_evaluation.raw.get("strategy", {})).get(
                    "raw_spec", detail.result.strategy_evaluation.raw.get("strategy_spec", {})
                )
                if isinstance(result.strategy_evaluation.raw, dict)
                else {},
                result.instance_id,
            ),
            htf_context=htf,
            context_consumption_trace=contexts,
            component_events=_component_events(result, start, end),
            long=sliced_side("long"),
            short=sliced_side("short"),
        )

    def chart_events(
        self,
        *,
        run_id: str,
        instance_id: str,
        from_ms: int,
        to_ms: int,
        context_overlay_ref: str | None = None,
    ) -> ChartEventsBundle:
        trace = self.signal_trace(
            run_id=run_id,
            instance_id=instance_id,
            from_ms=from_ms,
            to_ms=to_ms,
            context_overlay_ref=context_overlay_ref,
        )
        requested_from = from_ms // 1000
        requested_to = max(requested_from, (to_ms - 1) // 1000)
        actual_from = trace.times[0] if trace.times else requested_from
        actual_to = trace.times[-1] if trace.times else requested_to
        return ChartEventsBundle(
            times=trace.times,
            component_events=trace.component_events,
            htf_context=trace.htf_context,
            meta=trace.meta,
            coverage=ChartEventsCoverage(
                from_sec=actual_from,
                to_sec=actual_to,
                bar_count=len(trace.times),
                requested_from_sec=requested_from,
                requested_to_sec=requested_to,
                truncated=bool(trace.times)
                and (actual_from > requested_from or actual_to < requested_to),
            ),
        )

    def managed_policy_events(
        self,
        *,
        run_id: str,
        position_id: str | None = None,
    ) -> ManagedPolicyEventTrace:
        detail = self._runs.detail(run_id)
        trace = self._runs.managed_policy_events(run_id)
        if position_id is None:
            return trace
        known_position_ids = {
            position_execution.position.position_id
            for position_execution in detail.result.execution.positions
        }
        if detail.result.execution.final_open_position is not None:
            known_position_ids.add(detail.result.execution.final_open_position.position_id)
        if position_id not in known_position_ids:
            raise InvalidRequest(
                "position_id does not belong to this run",
                {"run_id": run_id, "position_id": position_id},
            )
        return trace.model_copy(
            update={
                "events": tuple(
                    event for event in trace.events if event.position_id == position_id
                ),
            }
        )
