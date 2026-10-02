"""Consume Strategy Engine managed-policy replay without recalculating strategy rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.contracts import (
    Candle,
    HistoricalManagedProjectionDTO,
    ManagedPhaseTransitionRuleDTO,
    ManagedReplayResult,
    ManagedRuntimeExitRuleDTO,
    ManagedStopActionRuleDTO,
    ManagedTakeActionRuleDTO,
    ManagedTransitionPathDTO,
    MarketFrame,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionSide, ExitCandidate, PositionState
from research_service.execution.managed_policy_events import ManagedPolicyEvent

_PHASES = ("initial_risk", "proven", "protected", "runner", "exhaustion")
_PHASE_RANK = {name: index for index, name in enumerate(_PHASES)}

# Round-trips through this module's own `_runtime_candidate_type`, so a
# projection-driven `ManagedEffectiveState` reaches the same
# `candidate_type` as a `/managed-replay`-driven one without that function
# needing to know about `exit_class` at all.
_EXIT_CLASS_TO_KIND = {
    "runtime_protective": "protective_exit",
    "runtime_take": "take_profit",
    "runtime_close": "market_close",
}


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


def build_managed_policy_timeline_from_projection(
    projection: HistoricalManagedProjectionDTO,
    position: PositionState,
    market_frame: MarketFrame,
) -> ManagedPolicyTimeline:
    """`historical-managed-projection-v1`'s generic managed lifecycle
    consumer -- the candidate-wide-projection counterpart to
    `build_managed_policy_timeline`, producing the identical
    `ManagedPolicyTimeline` shape without a `/managed-replay` call per
    opened trade. Dispatches on `rules[].kind` (and each variant's own
    closed enum) alone -- never on a `component_id`, never on a raw
    strategy parameter (this contract carries none).

    `active_stop_component_id`/`active_take_component_id`/
    `runtime_exit_components` are always `None` here: `component_id` is
    deliberately not part of this contract (design.md D2/D6), so this
    path cannot populate those attribution-only fields the way
    `build_managed_policy_timeline` does from `/managed-replay`'s raw
    events. They are diagnostic/reason-string fields only -- no exit
    arbitration or fill decision reads them.
    """

    entry_index = position.entry_fill.bar_index
    side = position.side
    entry_price = float(position.entry_fill.reference_price)
    candles = market_frame.candles
    target_index = len(candles) - 1

    phase_rules = [r for r in projection.rules if r.kind == "phase_transition"]
    stop_rules = [r for r in projection.rules if r.kind == "stop_action"]
    take_rules = [r for r in projection.rules if r.kind == "take_action"]
    runtime_rules = [r for r in projection.rules if r.kind == "runtime_exit"]

    phase = "initial_risk"
    active_stop_price: float | None = None
    active_stop_rule_id: str | None = None
    active_take_profile = "initial"
    active_take_rule_id: str | None = None
    best_price = entry_price
    worst_price = entry_price

    states: list[ManagedEffectiveState] = []
    for index in range(entry_index, target_index + 1):
        candle = candles[index]
        high, low = float(candle.high), float(candle.low)
        if side == "long":
            best_price = max(best_price, high)
            worst_price = min(worst_price, low)
            mfe_price = best_price
            mfe_pct = (best_price - entry_price) / entry_price
            mae_pct = (entry_price - worst_price) / entry_price
        else:
            best_price = min(best_price, low)
            worst_price = max(worst_price, high)
            mfe_price = best_price
            mfe_pct = (entry_price - best_price) / entry_price
            mae_pct = (worst_price - entry_price) / entry_price
        bars_in_trade = index - entry_index + 1
        mfe_distance = abs(mfe_price - entry_price)
        trade_metric_values = {
            "bars_since_entry": float(bars_in_trade),
            "mfe_pct": mfe_pct,
            "mfe_distance": mfe_distance,
        }

        for rule in phase_rules:
            if _PHASE_RANK[rule.target_phase] <= _PHASE_RANK[phase]:
                continue
            met, _path_id = _phase_rule_met(rule, projection, side, trade_metric_values, index)
            if met:
                phase = rule.target_phase

        candidates: list[tuple[float, str]] = []
        for stop_rule in stop_rules:
            if not _at_least(phase, stop_rule.activation_phase):
                continue
            distance = projection.distances[stop_rule.distance_id][index]
            if distance is None:
                continue
            price = entry_price + distance if side == "long" else entry_price - distance
            candidates.append((price, stop_rule.rule_id))
        if candidates:
            updated = _tightened_stop(candidates, side, active_stop_price)
            if updated is not None:
                active_stop_price, active_stop_rule_id = updated

        for take_rule in take_rules:
            if not _at_least(phase, take_rule.activation_phase):
                continue
            if take_rule.resulting_profile != active_take_profile:
                active_take_profile = take_rule.resulting_profile
                active_take_rule_id = take_rule.rule_id

        armed: list[str] = []
        runtime_kinds: dict[str, str] = {}
        for runtime_rule in runtime_rules:
            if not _at_least(phase, runtime_rule.activation_phase):
                continue
            series = projection.conditions[runtime_rule.condition_id]
            values = series.long if side == "long" else series.short
            start = index - runtime_rule.confirm_bars + 1
            if start < entry_index:
                continue
            if all(values[pos] for pos in range(start, index + 1)):
                armed.append(runtime_rule.rule_id)
                runtime_kinds[runtime_rule.rule_id] = _EXIT_CLASS_TO_KIND[runtime_rule.exit_class]

        if index == target_index:
            continue
        active_runtime_ids = tuple(armed)
        states.append(
            ManagedEffectiveState(
                trade_id=position.position_id,
                side=side,
                effective_time_ms=candles[index + 1].open_time_ms,
                source_bar_index=index,
                source_time_ms=candle.open_time_ms,
                phase=phase,
                bars_in_trade=bars_in_trade,
                mfe_pct=Decimal(str(mfe_pct)),
                mae_pct=Decimal(str(mae_pct)),
                active_stop_price=(
                    Decimal(str(active_stop_price)) if active_stop_price is not None else None
                ),
                active_stop_rule_id=active_stop_rule_id if active_stop_price is not None else None,
                active_stop_component_id=None,
                active_take_profile=active_take_profile,
                active_take_rule_id=active_take_rule_id,
                active_take_component_id=None,
                runtime_exit_rule_ids=active_runtime_ids,
                runtime_exit_components={rule_id: None for rule_id in active_runtime_ids},
                runtime_exit_kinds=runtime_kinds,
            )
        )

    return ManagedPolicyTimeline(
        trade_id=position.position_id,
        side=side,
        entry_time_ms=position.entry_fill.time_ms,
        states=tuple(states),
    )


@dataclass(frozen=True, slots=True)
class ManagedRuleSet:
    """Pre-filtered, per-kind view of a `HistoricalManagedProjection`'s
    `rules[]`, built once per candidate. `advance_managed_trade_state`
    is called once per bar for every open managed trade -- re-filtering
    `projection.rules` by kind on every one of those calls would put
    `len(rules)` back into the per-bar cost. This exists purely so that
    per-bar cost depends only on rule *count*, never on how many times
    the projection has already been consulted."""

    phase_transitions: tuple[ManagedPhaseTransitionRuleDTO, ...]
    stop_actions: tuple[ManagedStopActionRuleDTO, ...]
    take_actions: tuple[ManagedTakeActionRuleDTO, ...]
    runtime_exits: tuple[ManagedRuntimeExitRuleDTO, ...]

    @classmethod
    def from_projection(cls, projection: HistoricalManagedProjectionDTO) -> "ManagedRuleSet":
        return cls(
            phase_transitions=tuple(
                r for r in projection.rules if r.kind == "phase_transition"
            ),
            stop_actions=tuple(r for r in projection.rules if r.kind == "stop_action"),
            take_actions=tuple(r for r in projection.rules if r.kind == "take_action"),
            runtime_exits=tuple(r for r in projection.rules if r.kind == "runtime_exit"),
        )


@dataclass(slots=True)
class ManagedTradeState:
    """One open trade's managed-policy state, advanced one bar at a
    time (`historical-managed-projection-v1` design.md amendment:
    "Historical projection consumption SHALL be incremental over the
    actual open-trade lifetime"). Lives exactly as long as the position
    it belongs to -- created at entry, discarded at exit. Never holds
    anything proportional to the candidate's total bar count."""

    side: ExecutionSide
    entry_index: int
    entry_price: float
    phase: str = "initial_risk"
    active_stop_price: float | None = None
    active_stop_rule_id: str | None = None
    active_take_profile: str = "initial"
    active_take_rule_id: str | None = None
    best_price: float = 0.0
    worst_price: float = 0.0
    # rule_id -> consecutive true-bar count of that rule's condition,
    # since entry. Equivalent to (and replaces) recomputing "all true in
    # the trailing confirm_bars window" from scratch every bar: a count
    # that resets to 0 on a false bar and increments on a true bar has
    # length exactly equal to the current true-run, and the run can never
    # extend past entry_index because the counter starts at entry. This
    # reproduces managed.py's entry-anchored window exactly (proven by
    # the eager `build_managed_policy_timeline_from_projection`, which
    # this incremental path is parity-tested against), without ever
    # re-scanning a window.
    confirmation_counts: dict[str, int] = field(default_factory=dict)


def initialize_managed_trade_state(position: PositionState) -> ManagedTradeState:
    entry_price = float(position.entry_fill.reference_price)
    return ManagedTradeState(
        side=position.side,
        entry_index=position.entry_fill.bar_index,
        entry_price=entry_price,
        best_price=entry_price,
        worst_price=entry_price,
    )


def advance_managed_trade_state(
    state: ManagedTradeState,
    projection: HistoricalManagedProjectionDTO,
    rule_set: ManagedRuleSet,
    *,
    trade_id: str,
    bar_index: int,
    source_time_ms: int,
    high: float,
    low: float,
    next_time_ms: int | None,
    close: float | None = None,
    event_sink: list[ManagedPolicyEvent] | None = None,
) -> tuple[ManagedTradeState, ManagedEffectiveState | None]:
    """Advance one open trade's managed state by exactly one bar.

    Mirrors `build_managed_policy_timeline_from_projection`'s per-index
    loop body formula-for-formula (that function stays as the parity
    oracle for this one, per design.md -- it is no longer the
    production historical hot path). `next_time_ms` is the bar this
    step's decisions become effective on (`None` only when `bar_index`
    is the last bar in the market frame, matching the eager builder's
    own "no state for the final bar" rule); when it's `None` this
    returns `(new_state, None)` -- the caller has nothing to act on
    next bar because there is no next bar.

    `event_sink` (`historical-managed-projection-cutover-v1` design D5):
    when given, this bar's managed-policy events are appended to it.
    Events are observations of the state transitions this consumer has
    just produced, not a second implementation of Strategy Engine
    policy: one `phase_changed` per fired rule (`metadata.path_id` for a
    paths rule), `active_stop_updated` when the active stop actually
    moved, `active_take_updated` on a profile change, and
    `runtime_exit_triggered` on every bar a runtime rule is armed.
    Event-only prices (the MFE price on `phase_changed`, `close` on
    `runtime_exit_triggered`) are diagnostic derivations from this
    state and the market bar; nothing reads them back into a decision.
    `None` (the default) skips event construction entirely."""

    if event_sink is not None and close is None:
        raise ValueError("close is required when event_sink is given")

    side = state.side
    entry_price = state.entry_price
    if side == "long":
        best_price = max(state.best_price, high)
        worst_price = min(state.worst_price, low)
        mfe_price = best_price
        mfe_pct = (best_price - entry_price) / entry_price
        mae_pct = (entry_price - worst_price) / entry_price
    else:
        best_price = min(state.best_price, low)
        worst_price = max(state.worst_price, high)
        mfe_price = best_price
        mfe_pct = (entry_price - best_price) / entry_price
        mae_pct = (worst_price - entry_price) / entry_price
    bars_in_trade = bar_index - state.entry_index + 1
    mfe_distance = abs(mfe_price - entry_price)
    trade_metric_values = {
        "bars_since_entry": float(bars_in_trade),
        "mfe_pct": mfe_pct,
        "mfe_distance": mfe_distance,
    }

    phase = state.phase
    for rule in rule_set.phase_transitions:
        if _PHASE_RANK[rule.target_phase] <= _PHASE_RANK[phase]:
            continue
        met, path_id = _phase_rule_met(rule, projection, side, trade_metric_values, bar_index)
        if met:
            if event_sink is not None:
                event_sink.append(
                    _event(
                        state,
                        trade_id,
                        source_time_ms,
                        bar_index,
                        "phase_changed",
                        rule.rule_id,
                        from_phase=phase,
                        to_phase=rule.target_phase,
                        price=mfe_price,
                        metadata={"path_id": path_id} if path_id is not None else {},
                    )
                )
            phase = rule.target_phase

    candidates: list[tuple[float, str]] = []
    for stop_rule in rule_set.stop_actions:
        if not _at_least(phase, stop_rule.activation_phase):
            continue
        distance = projection.distances[stop_rule.distance_id][bar_index]
        if distance is None:
            continue
        price = entry_price + distance if side == "long" else entry_price - distance
        candidates.append((price, stop_rule.rule_id))
    active_stop_price = state.active_stop_price
    active_stop_rule_id = state.active_stop_rule_id
    if candidates:
        updated = _tightened_stop(candidates, side, active_stop_price)
        if updated is not None:
            active_stop_price, active_stop_rule_id = updated
            if event_sink is not None:
                event_sink.append(
                    _event(
                        state,
                        trade_id,
                        source_time_ms,
                        bar_index,
                        "active_stop_updated",
                        active_stop_rule_id,
                        price=active_stop_price,
                        metadata={"effective_from_bar": bar_index + 1},
                    )
                )

    active_take_profile = state.active_take_profile
    active_take_rule_id = state.active_take_rule_id
    for take_rule in rule_set.take_actions:
        if not _at_least(phase, take_rule.activation_phase):
            continue
        if take_rule.resulting_profile != active_take_profile:
            active_take_profile = take_rule.resulting_profile
            active_take_rule_id = take_rule.rule_id
            if event_sink is not None:
                event_sink.append(
                    _event(
                        state,
                        trade_id,
                        source_time_ms,
                        bar_index,
                        "active_take_updated",
                        take_rule.rule_id,
                        metadata={
                            "take_profile": active_take_profile,
                            "effective_from_bar": bar_index + 1,
                        },
                    )
                )

    confirmation_counts = dict(state.confirmation_counts)
    armed: list[str] = []
    runtime_kinds: dict[str, str] = {}
    for runtime_rule in rule_set.runtime_exits:
        # The confirm-bars counter tracks the condition series alone,
        # every bar, regardless of phase -- exactly like the eager
        # builder's window, whose `all(values[start:index+1])` never
        # itself checked phase at each window position, only at the
        # current bar (see docstring above).
        series = projection.conditions[runtime_rule.condition_id]
        value = (series.long if side == "long" else series.short)[bar_index]
        count = confirmation_counts.get(runtime_rule.rule_id, 0)
        count = count + 1 if value else 0
        confirmation_counts[runtime_rule.rule_id] = count
        if _at_least(phase, runtime_rule.activation_phase) and count >= runtime_rule.confirm_bars:
            armed.append(runtime_rule.rule_id)
            runtime_kinds[runtime_rule.rule_id] = _EXIT_CLASS_TO_KIND[runtime_rule.exit_class]
            if event_sink is not None:
                event_sink.append(
                    _event(
                        state,
                        trade_id,
                        source_time_ms,
                        bar_index,
                        "runtime_exit_triggered",
                        runtime_rule.rule_id,
                        price=close,
                        metadata={
                            "exit_kind": runtime_kinds[runtime_rule.rule_id],
                            "effective_from_bar": bar_index + 1,
                        },
                    )
                )

    new_state = ManagedTradeState(
        side=side,
        entry_index=state.entry_index,
        entry_price=entry_price,
        phase=phase,
        active_stop_price=active_stop_price,
        active_stop_rule_id=active_stop_rule_id,
        active_take_profile=active_take_profile,
        active_take_rule_id=active_take_rule_id,
        best_price=best_price,
        worst_price=worst_price,
        confirmation_counts=confirmation_counts,
    )

    if next_time_ms is None:
        return new_state, None

    active_runtime_ids = tuple(armed)
    effective = ManagedEffectiveState(
        trade_id=trade_id,
        side=side,
        effective_time_ms=next_time_ms,
        source_bar_index=bar_index,
        source_time_ms=source_time_ms,
        phase=phase,
        bars_in_trade=bars_in_trade,
        mfe_pct=Decimal(str(mfe_pct)),
        mae_pct=Decimal(str(mae_pct)),
        active_stop_price=(
            Decimal(str(active_stop_price)) if active_stop_price is not None else None
        ),
        active_stop_rule_id=active_stop_rule_id if active_stop_price is not None else None,
        active_stop_component_id=None,
        active_take_profile=active_take_profile,
        active_take_rule_id=active_take_rule_id,
        active_take_component_id=None,
        runtime_exit_rule_ids=active_runtime_ids,
        runtime_exit_components={rule_id: None for rule_id in active_runtime_ids},
        runtime_exit_kinds=runtime_kinds,
    )
    return new_state, effective


def _phase_rule_met(
    rule: ManagedPhaseTransitionRuleDTO,
    projection: HistoricalManagedProjectionDTO,
    side: ExecutionSide,
    trade_metric_values: Mapping[str, float],
    index: int,
) -> tuple[bool, str | None]:
    """Whether one phase rule's condition holds on bar `index`, and the
    attributed `path_id` for a paths rule (`historical-managed-
    projection-cutover-v1` design D2). Checks the atomic forms first, so
    atomic rules pay nothing for the paths form. Generic by construction:
    only opaque ids, series and the consumer's own trade metrics."""

    if rule.condition_id is not None:
        return _condition_value(projection, rule.condition_id, side, index), None
    if rule.distance_id is not None:
        assert rule.trade_metric is not None
        return (
            _threshold_met(
                projection, rule.distance_id, rule.trade_metric, trade_metric_values, index
            ),
            None,
        )
    assert rule.paths is not None
    for path in rule.paths:
        if _path_met(projection, path, side, trade_metric_values, index):
            return True, path.path_id
    return False, None


def _path_met(
    projection: HistoricalManagedProjectionDTO,
    path: ManagedTransitionPathDTO,
    side: ExecutionSide,
    trade_metric_values: Mapping[str, float],
    index: int,
) -> bool:
    if path.condition_id is not None and not _condition_value(
        projection, path.condition_id, side, index
    ):
        return False
    for item in path.thresholds:
        if not _threshold_met(
            projection, item.distance_id, item.trade_metric, trade_metric_values, index
        ):
            return False
    at_least = path.at_least
    if at_least is None:
        return True
    count = 0
    for term in at_least.terms:
        if term.condition_id is not None:
            count += _condition_value(projection, term.condition_id, side, index)
        else:
            assert term.distance_id is not None and term.trade_metric is not None
            count += _threshold_met(
                projection, term.distance_id, term.trade_metric, trade_metric_values, index
            )
    return count >= at_least.k


def _condition_value(
    projection: HistoricalManagedProjectionDTO,
    condition_id: str,
    side: ExecutionSide,
    index: int,
) -> bool:
    series = projection.conditions[condition_id]
    return (series.long if side == "long" else series.short)[index]


def _threshold_met(
    projection: HistoricalManagedProjectionDTO,
    distance_id: str,
    trade_metric: str,
    trade_metric_values: Mapping[str, float],
    index: int,
) -> bool:
    threshold = projection.distances[distance_id][index]
    return threshold is not None and trade_metric_values[trade_metric] >= threshold


def _tightened_stop(
    candidates: list[tuple[float, str]],
    side: ExecutionSide,
    active_stop_price: float | None,
) -> tuple[float, str] | None:
    """The new `(active_stop_price, active_stop_rule_id)`, or `None` when
    the stop does not move. Mirrors Strategy Engine's managed replay
    (`historical-managed-projection-cutover-v1` design D3): the stop and
    its rule id change only when the tightened price moves by more than
    `1e-8`, so a non-tightening candidate never re-labels the active
    stop."""

    chosen_price, chosen_rule_id = (
        max(candidates, key=lambda item: item[0])
        if side == "long"
        else min(candidates, key=lambda item: item[0])
    )
    if active_stop_price is None:
        return chosen_price, chosen_rule_id
    tightened = (
        max(active_stop_price, chosen_price)
        if side == "long"
        else min(active_stop_price, chosen_price)
    )
    if abs(tightened - active_stop_price) > 1e-8:
        return tightened, chosen_rule_id
    return None


def _event(
    state: ManagedTradeState,
    trade_id: str,
    time_ms: int,
    bar_index: int,
    event_type: str,
    rule_id: str | None,
    *,
    from_phase: str | None = None,
    to_phase: str | None = None,
    price: float | None = None,
    metadata: dict[str, object] | None = None,
) -> ManagedPolicyEvent:
    return ManagedPolicyEvent(
        position_id=trade_id,
        side=state.side,
        time_ms=time_ms,
        bar_index=bar_index,
        event_type=event_type,  # type: ignore[arg-type]
        rule_id=rule_id,
        component_id=None,
        from_phase=from_phase,
        to_phase=to_phase,
        price=Decimal(str(price)) if price is not None else None,
        metadata=metadata or {},
    )


def _at_least(current: str, threshold: str) -> bool:
    if not threshold:
        return True
    return _PHASE_RANK[current] >= _PHASE_RANK[threshold]


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
    """Continuous-market level fill (`research-managed-policy-consumption-v1`
    "Managed stop execution"): the managed stop fills at exactly its
    level whenever the bar reached it, never at the open."""

    if side == "long":
        return level if candle.low <= level else None
    return level if candle.high >= level else None


def _runtime_candidate_type(
    exit_kind: str,
) -> Literal["runtime_protective", "runtime_take", "runtime_close"]:
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
