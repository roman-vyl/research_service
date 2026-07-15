"""Consume Strategy Engine managed-policy replay without recalculating strategy rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.contracts import Candle, ManagedReplayResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionSide, ExitCandidate, PositionState


class ManagedEffectiveState(BaseModel):
    """Managed policy state inherited at the start of one executable bar."""

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1)
    side: ExecutionSide
    effective_time_ms: int = Field(ge=0)
    source_bar_index: int = Field(ge=0)
    source_time_ms: int = Field(ge=0)
    phase: str = Field(min_length=1)
    bars_in_trade: int = Field(ge=1)
    mfe_pct: Decimal
    mae_pct: Decimal
    active_stop_price: Decimal | None = Field(default=None, gt=0)
    active_stop_rule_id: str | None = None
    active_stop_component_id: str | None = None
    active_take_profile: str = Field(min_length=1)
    active_take_rule_id: str | None = None
    active_take_component_id: str | None = None
    runtime_exit_rule_ids: tuple[str, ...] = ()
    runtime_exit_components: dict[str, str | None] = Field(default_factory=dict)
    runtime_exit_kinds: dict[str, str] = Field(default_factory=dict)


class ManagedPolicyTimeline(BaseModel):
    """Effective managed states keyed by the bar on which they may execute."""

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1)
    side: ExecutionSide
    entry_time_ms: int = Field(ge=0)
    states: tuple[ManagedEffectiveState, ...]

    def state_for_time(self, time_ms: int) -> ManagedEffectiveState | None:
        for state in self.states:
            if state.effective_time_ms == time_ms:
                return state
        return None


def build_managed_policy_timeline(
    replay: ManagedReplayResult,
    position: PositionState,
) -> ManagedPolicyTimeline:
    """Shift end-of-bar decisions onto the next executable bar.

    Strategy Engine owns phase/rule evaluation. Research Service only carries
    the resulting state forward to ``effective_from_time_ms``.
    """

    if replay.trade_id != position.position_id:
        raise InvalidRequest("managed replay belongs to another position")
    if replay.side != position.side:
        raise InvalidRequest("managed replay side differs from position side")
    if replay.entry_time_ms != position.entry_fill.time_ms:
        raise InvalidRequest("managed replay entry time differs from position")

    stop_rule_id: str | None = None
    stop_component_id: str | None = None
    take_rule_id: str | None = None
    take_component_id: str | None = None
    runtime_components: dict[str, str | None] = {}
    runtime_kinds: dict[str, str] = {}
    events_by_source_bar: dict[int, list[Mapping[str, object]]] = {}
    for raw_event in replay.events:
        source_bar = raw_event.get("bar_index")
        if isinstance(source_bar, int):
            events_by_source_bar.setdefault(source_bar, []).append(raw_event)

    states: list[ManagedEffectiveState] = []
    for bar in replay.bars:
        for event in events_by_source_bar.get(bar.bar_index, []):
            event_type = str(event.get("event_type", ""))
            rule_id = _optional_text(event.get("rule_id"))
            component_id = _optional_text(event.get("component_id"))
            metadata = event.get("metadata")
            metadata_map = metadata if isinstance(metadata, Mapping) else {}
            if event_type == "active_stop_updated":
                stop_rule_id = rule_id
                stop_component_id = component_id
            elif event_type == "active_take_updated":
                take_rule_id = rule_id
                take_component_id = component_id
            elif event_type == "runtime_exit_triggered" and rule_id is not None:
                runtime_components[rule_id] = component_id
                runtime_kinds[rule_id] = str(metadata_map.get("exit_kind", "market_close"))

        if bar.effective_from_time_ms is None:
            continue
        active_runtime_ids = tuple(bar.runtime_exit_rule_ids)
        states.append(
            ManagedEffectiveState(
                trade_id=replay.trade_id,
                side=position.side,
                effective_time_ms=bar.effective_from_time_ms,
                source_bar_index=bar.bar_index,
                source_time_ms=bar.time_ms,
                phase=bar.phase,
                bars_in_trade=bar.bars_in_trade,
                mfe_pct=bar.mfe_pct,
                mae_pct=bar.mae_pct,
                active_stop_price=bar.active_stop_price,
                active_stop_rule_id=stop_rule_id if bar.active_stop_price is not None else None,
                active_stop_component_id=(
                    stop_component_id if bar.active_stop_price is not None else None
                ),
                active_take_profile=bar.active_take_profile,
                active_take_rule_id=take_rule_id,
                active_take_component_id=take_component_id,
                runtime_exit_rule_ids=active_runtime_ids,
                runtime_exit_components={
                    rule_id: runtime_components.get(rule_id) for rule_id in active_runtime_ids
                },
                runtime_exit_kinds={
                    rule_id: runtime_kinds.get(rule_id, "market_close")
                    for rule_id in active_runtime_ids
                },
            )
        )

    return ManagedPolicyTimeline(
        trade_id=replay.trade_id,
        side=position.side,
        entry_time_ms=replay.entry_time_ms,
        states=tuple(states),
    )


def collect_managed_exit_candidates(
    position: PositionState,
    candle: Candle,
    state: ManagedEffectiveState | None,
    *,
    bar_index: int,
) -> tuple[ExitCandidate, ...]:
    """Convert inherited managed state into executable bar-open candidates."""

    if state is None:
        return ()
    if state.trade_id != position.position_id or state.side != position.side:
        raise InvalidRequest("managed effective state belongs to another position")
    if state.effective_time_ms != candle.open_time_ms:
        raise InvalidRequest("managed state is not effective on this candle")
    if bar_index <= position.entry_fill.bar_index:
        return ()

    candidates: list[ExitCandidate] = []
    if state.active_stop_price is not None:
        fill_price = _managed_stop_fill(
            position.side,
            candle,
            level=state.active_stop_price,
        )
        if fill_price is not None:
            candidates.append(
                ExitCandidate(
                    candidate_type="managed_stop",
                    layer="exit_management",
                    bar_index=bar_index,
                    time_ms=candle.open_time_ms,
                    reference_level=state.active_stop_price,
                    fill_price=fill_price,
                    reason=f"active_stop:{state.active_stop_component_id or 'managed_stop'}",
                    rule_id=state.active_stop_rule_id,
                    component_id=state.active_stop_component_id,
                    exit_kind="protective_stop",
                )
            )

    for rule_id in state.runtime_exit_rule_ids:
        exit_kind = state.runtime_exit_kinds.get(rule_id, "market_close")
        candidates.append(
            ExitCandidate(
                candidate_type=_runtime_candidate_type(exit_kind),
                layer="exit_management",
                bar_index=bar_index,
                time_ms=candle.open_time_ms,
                reference_level=candle.close,
                fill_price=candle.close,
                reason=f"runtime_exit:{exit_kind}",
                rule_id=rule_id,
                component_id=state.runtime_exit_components.get(rule_id),
                exit_kind=exit_kind,
            )
        )

    return tuple(candidates)


def _managed_stop_fill(
    side: ExecutionSide,
    candle: Candle,
    *,
    level: Decimal,
) -> Decimal | None:
    if side == "long":
        if candle.open <= level:
            return candle.open
        if candle.low <= level <= candle.high:
            return level
    else:
        if level <= candle.open:
            return candle.open
        if candle.low <= level <= candle.high:
            return level
    return None


def _runtime_candidate_type(exit_kind: str) -> str:
    if exit_kind == "protective_exit":
        return "runtime_protective"
    if exit_kind == "take_profit":
        return "runtime_take"
    return "runtime_close"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
