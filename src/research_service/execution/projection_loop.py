"""Projection-driven unified bar-by-bar execution loop (I4,
`compact-strategy-evaluation-boundary-v1`).

`run_projection_execution_loop` is the `HistoricalExecutionProjection`
counterpart to `execution/loop.py::run_unified_execution_loop` --
identical intra-bar ordering and same-bar arbitration priority
(`stop_loss < managed_stop < take_profit < ... < signal`, reused
unchanged from `execution/unified_exits.py`), different source of
strategy facts (`HistoricalExecutionProjectionIndex` instead of a
dense `StrategyEvaluationResult`).

Not wired into production orchestration. Production `/range`
consumption, `/range-batch`, and coordinated cutover remain I7 -- this
is a parallel, in-process/fixture-driven entrypoint proving execution-
loop-level semantic parity (I4's own gate), reachable today only from
tests.
"""

from __future__ import annotations

from collections.abc import Callable

from research_service.domain.contracts import (
    HistoricalExecutionProjectionIndex,
    ManagedReplayResult,
    MarketFrame,
)
from research_service.domain.errors import InvalidRequest, UpstreamServiceError
from research_service.domain.execution import (
    ExecutionEvent,
    ExecutionLoopResult,
    ExecutionPolicy,
    ExitArbitrationResult,
    ExitFill,
    PositionExecution,
    PositionState,
)
from research_service.execution.managed_policy_events import ManagedPolicyEvent
from research_service.execution.managed_policy import (
    ManagedEffectiveState,
    ManagedPolicyTimeline,
    ManagedRuleSet,
    ManagedTradeState,
    advance_managed_trade_state,
    build_managed_policy_timeline,
    collect_managed_exit_candidates,
    initialize_managed_trade_state,
)
from research_service.execution.projection_entry import (
    EntryQuantityProvider,
    try_open_projection_position,
)
from research_service.execution.projection_static_exits import (
    collect_projection_static_exit_candidates,
)
from research_service.execution.unified_exits import (
    arbitrate_unified_exit_candidates,
    execute_unified_exit,
)

ManagedReplayProvider = Callable[[PositionState], ManagedReplayResult | None]
ClosedPositionConsumer = Callable[[PositionExecution], None]


def run_projection_execution_loop(
    instance_id: str,
    projection_index: HistoricalExecutionProjectionIndex,
    market_frame: MarketFrame,
    policy: ExecutionPolicy,
    *,
    entry_quantity_provider: EntryQuantityProvider,
    managed_replay_provider: ManagedReplayProvider | None = None,
    allow_legacy_managed_replay_fallback: bool = False,
    closed_position_consumer: ClosedPositionConsumer | None = None,
    managed_event_sink: list[ManagedPolicyEvent] | None = None,
) -> ExecutionLoopResult:
    """Execute one strategy instance against a validated, indexed
    `HistoricalExecutionProjection` across an aligned market range.

    Ordering mirrors `run_unified_execution_loop` exactly:

    1. a position that existed at bar open may exit on that bar;
    2. a bar that began with an open position cannot also open a
       replacement;
    3. a position opened on the current close cannot exit on the same
       bar;
    4. managed decisions are consumed only through their next-bar
       timeline.

    Callers are responsible for having already run
    `validate_projection_alignment` on `projection_index.projection`
    against this exact `market_frame`/`instance_id`'s strategy identity
    before calling this function -- this loop trusts an already-aligned
    index, matching how `run_unified_execution_loop` trusts an already-
    validated `StrategyEvaluationResult`.

    Managed-policy resolution (`historical-managed-projection-v1`)
    fails closed by default: if `managed_replay_provider` is given (the
    caller intends managed execution for this run) but a position's
    acquired projection carries no `HistoricalManagedProjection`, this
    raises `UpstreamServiceError` rather than silently falling back to
    a per-position `/managed-replay` call -- that per-trade call is the
    exact O(trades x full-history evaluation) pathology this contract
    exists to eliminate, so its absence must never go unnoticed in a
    production historical run. Pass `allow_legacy_managed_replay_fallback=True`
    only for an explicit parity/oracle comparison run (e.g. I4's own
    execution-loop parity tests) that deliberately exercises the old
    per-trade path against a projection fixture with no `managed` data.

    `managed_event_sink` (`historical-managed-projection-cutover-v1`
    design D5): when given, the local projection path appends every
    managed-policy event it produces to it. The legacy oracle path
    captures its events from `/managed-replay` responses instead (see
    `MaterializeBacktestProjectionOutcome._managed_provider`).
    """

    if projection_index.projection.bar_count != len(market_frame.candles):
        raise InvalidRequest("Historical execution projection bar count differs from market frame")

    # Built once per candidate (the projection never changes across this
    # loop's positions), not once per bar or per trade -- see
    # ManagedRuleSet's own docstring.
    managed_projection = projection_index.projection.managed
    rule_set = ManagedRuleSet.from_projection(managed_projection) if managed_projection is not None else None

    current_position: PositionState | None = None
    # Exactly one of these two is ever non-None at a time: the legacy
    # eager timeline (oracle/parity-only, `allow_legacy_managed_replay_fallback=True`)
    # or the incremental per-bar trade state (production default, "SHALL be
    # incremental over the actual open-trade lifetime" -- see managed_policy.py
    # module docstring amendment).
    current_managed_timeline: ManagedPolicyTimeline | None = None
    current_managed_trade_state: ManagedTradeState | None = None
    current_managed_effective: ManagedEffectiveState | None = None
    completed: list[PositionExecution] = []
    events: list[ExecutionEvent] = []

    for bar_index, candle in enumerate(market_frame.candles):
        position_was_open_at_bar_start = current_position is not None

        if current_position is not None:
            managed_state = (
                current_managed_timeline.state_for_time(candle.open_time_ms)
                if current_managed_timeline is not None
                else current_managed_effective
            )
            active_take_profile = (
                managed_state.active_take_profile if managed_state is not None else "initial"
            )
            static_candidates = collect_projection_static_exit_candidates(
                projection_index,
                current_position,
                candle,
                bar_index=bar_index,
                active_take_profile=active_take_profile,
            )
            managed_candidates = collect_managed_exit_candidates(
                current_position,
                candle,
                managed_state,
                bar_index=bar_index,
            )
            arbitration = arbitrate_unified_exit_candidates(
                (*static_candidates, *managed_candidates)
            )
            exit_fill = execute_unified_exit(current_position, arbitration)
            if exit_fill is not None:
                closed_execution = PositionExecution(
                        position=current_position,
                        status="closed",
                        exit_fill=exit_fill,
                        exit_arbitration=arbitration,
                    )
                completed.append(closed_execution)
                if closed_position_consumer is not None:
                    closed_position_consumer(closed_execution)
                events.append(
                    _exit_event(current_position, exit_fill=exit_fill, arbitration=arbitration)
                )
                current_position = None
                current_managed_timeline = None
                current_managed_trade_state = None
                current_managed_effective = None

        # Same legacy invariant as run_unified_execution_loop: a position
        # present at bar open blocks replacement entry on that same bar,
        # even when it was closed during arbitration above.
        if not position_was_open_at_bar_start:
            opened = try_open_projection_position(
                projection_index,
                market_frame,
                policy,
                instance_id=instance_id,
                bar_index=bar_index,
                current_position=current_position,
                entry_quantity_provider=entry_quantity_provider,
            )
            if opened is not None and opened is not current_position:
                current_position = opened
                current_managed_timeline, current_managed_trade_state = _open_managed_state(
                    opened,
                    projection_index=projection_index,
                    managed_replay_provider=managed_replay_provider,
                    allow_legacy_managed_replay_fallback=allow_legacy_managed_replay_fallback,
                )
                current_managed_effective = None
                events.append(_entry_event(opened))

        # Advance the incremental trade state exactly one bar -- for a
        # position that survived the exit-check above, or one that just
        # opened this bar (its own entry-bar snapshot, effective starting
        # next bar, matching the eager builder's original convention).
        # Never runs for the legacy-timeline path (that one is pre-built
        # in full at `_open_managed_state`) or for a position that closed
        # this bar (state already discarded above).
        if current_position is not None and current_managed_trade_state is not None:
            assert managed_projection is not None and rule_set is not None
            next_time_ms = (
                market_frame.candles[bar_index + 1].open_time_ms
                if bar_index + 1 < len(market_frame.candles)
                else None
            )
            current_managed_trade_state, current_managed_effective = advance_managed_trade_state(
                current_managed_trade_state,
                managed_projection,
                rule_set,
                trade_id=current_position.position_id,
                bar_index=bar_index,
                source_time_ms=candle.open_time_ms,
                high=float(candle.high),
                low=float(candle.low),
                next_time_ms=next_time_ms,
                close=float(candle.close),
                event_sink=managed_event_sink,
            )

    if current_position is not None:
        completed.append(PositionExecution(position=current_position, status="open"))
        last_candle = market_frame.candles[-1]
        events.append(
            ExecutionEvent(
                event_id=f"open:{current_position.position_id}:{last_candle.open_time_ms}",
                event_type="position_left_open",
                instance_id=current_position.instance_id,
                position_id=current_position.position_id,
                side=current_position.side,
                bar_index=len(market_frame.candles) - 1,
                time_ms=last_candle.open_time_ms,
                metadata={
                    "last_close": str(last_candle.close),
                    "entry_bar_index": current_position.entry_fill.bar_index,
                    "locked_exit_profile": current_position.locked_exit_profile,
                },
            )
        )

    return ExecutionLoopResult(
        instance_id=instance_id,
        market=market_frame.market,
        positions=tuple(completed),
        events=tuple(events),
        final_open_position=current_position,
    )


def _open_managed_state(
    position: PositionState,
    *,
    projection_index: HistoricalExecutionProjectionIndex,
    managed_replay_provider: ManagedReplayProvider | None,
    allow_legacy_managed_replay_fallback: bool,
) -> tuple[ManagedPolicyTimeline | None, ManagedTradeState | None]:
    """`historical-managed-projection-v1`: when the candidate-wide
    projection already carries a `HistoricalManagedProjection`
    (`exit_management.mode == "managed"`), initialize the new
    incremental per-bar trade state -- no Strategy Engine call, and no
    eager full-range materialization either (design.md amendment:
    "Historical Research execution SHALL NOT eagerly materialize
    managed state from each entry through the remainder of the
    requested market range"). This is unconditional production
    behaviour (`allow_legacy_managed_replay_fallback=False`, the
    default): `managed` present -> incremental path, always.

    `managed_replay_provider` being non-`None` is this loop's only
    signal that the caller wants managed execution for this position
    at all (a non-managed candidate never supplies one, and this
    function returns `(None, None)` immediately for it, silently, same
    as always). Once a caller HAS supplied it, a missing `managed`
    projection is a contract violation, not a reason to quietly fall
    back to the per-trade `/managed-replay` call -- that call is
    exactly the eliminated O(trades x full-history evaluation) path.
    It fails closed unless `allow_legacy_managed_replay_fallback` was
    explicitly set.

    `allow_legacy_managed_replay_fallback=True` is a genuine oracle
    override, not just a missing-`managed` rescue: it forces the
    legacy eager `/managed-replay`-sourced `ManagedPolicyTimeline` path
    even when `managed` IS present, so a caller can run the same real
    managed candidate through both paths and diff them (5.2's OLD-vs-
    NEW parity check) -- never the production default. `state_for_time`
    (O(states) per call) stays on this path only; it is never reached
    by production historical execution."""

    # Gating first (`historical-managed-projection-cutover-v1` design D4):
    # no provider means the caller did not request managed execution
    # (`managed_policy_enabled=False` or a non-managed run), whatever the
    # projection carries.
    if managed_replay_provider is None:
        return None, None
    managed = projection_index.projection.managed
    if managed is not None and not allow_legacy_managed_replay_fallback:
        return None, initialize_managed_trade_state(position)
    if managed is None and not allow_legacy_managed_replay_fallback:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message=(
                "Managed historical execution was requested but the acquired "
                "projection carries no HistoricalManagedProjection; refusing to "
                "fall back to a per-trade /managed-replay call"
            ),
            details={
                "position_id": position.position_id,
                "instance_id": position.instance_id,
                "strategy_id": projection_index.projection.strategy_id,
            },
        )
    replay = managed_replay_provider(position)
    if replay is None:
        return None, None
    return build_managed_policy_timeline(replay, position), None


def _entry_event(position: PositionState) -> ExecutionEvent:
    fill = position.entry_fill
    return ExecutionEvent(
        event_id=f"event:{fill.fill_id}",
        event_type="entry_filled",
        instance_id=position.instance_id,
        position_id=position.position_id,
        side=position.side,
        bar_index=fill.bar_index,
        time_ms=fill.time_ms,
        fill_id=fill.fill_id,
        metadata={
            "reference_price": str(fill.reference_price),
            "fill_price": str(fill.fill_price),
            "quantity": str(fill.quantity),
            "stop_loss_price": _decimal_text(position.initial_protection.stop_loss_price),
            "take_profit_price": _decimal_text(position.initial_protection.take_profit_price),
            "locked_exit_profile": position.locked_exit_profile,
        },
    )


def _exit_event(
    position: PositionState,
    *,
    exit_fill: ExitFill,
    arbitration: ExitArbitrationResult,
) -> ExecutionEvent:
    winner = arbitration.winner
    assert winner is not None
    return ExecutionEvent(
        event_id=f"event:{exit_fill.fill_id}",
        event_type="exit_filled",
        instance_id=position.instance_id,
        position_id=position.position_id,
        side=position.side,
        bar_index=exit_fill.bar_index,
        time_ms=exit_fill.time_ms,
        fill_id=exit_fill.fill_id,
        metadata={
            "candidate_type": exit_fill.candidate_type,
            "layer": exit_fill.layer,
            "reason": exit_fill.reason,
            "reference_level": str(exit_fill.reference_level),
            "fill_price": str(exit_fill.fill_price),
            "rule_id": exit_fill.rule_id,
            "component_id": exit_fill.component_id,
            "exit_kind": exit_fill.exit_kind,
            "exit_layer": exit_fill.layer,
            "locked_exit_profile": position.locked_exit_profile,
            "losing_candidate_types": [
                candidate.candidate_type for candidate in arbitration.losing_candidates
            ],
            "winner_reason": winner.reason,
        },
    )


def _decimal_text(value: object) -> str | None:
    return None if value is None else str(value)
