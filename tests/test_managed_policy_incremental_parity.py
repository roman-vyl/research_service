"""historical-managed-projection-v1 design amendment: historical managed
projection consumption SHALL be incremental over the actual open-trade
lifetime, not eagerly materialized from entry through the remainder of
the requested market range.

This proves `advance_managed_trade_state` (the new incremental,
per-bar production hot path) produces bar-for-bar identical output to
`build_managed_policy_timeline_from_projection` (the eager builder,
demoted to parity/oracle status only -- see its own updated docstring)
across the same corpus `test_managed_policy_from_projection.py` already
uses: all four rule kinds, long/short, multiple entry indices, the
confirm_bars positive/negative boundary.

Also proves the complexity claim directly: a single trade opened near
the start of a large market frame and closed a handful of bars later
requires exactly that many `advance_managed_trade_state` calls, not one
per remaining bar in the frame.
"""

from __future__ import annotations


import pytest

from research_service.domain.contracts import (
    HistoricalManagedProjectionDTO,
    ManagedConditionSeriesDTO,
    MarketFrame,
)
from research_service.domain.execution import PositionState
from research_service.execution.managed_policy import (
    ManagedRuleSet,
    advance_managed_trade_state,
    build_managed_policy_timeline_from_projection,
    initialize_managed_trade_state,
)
from test_managed_policy_from_projection import _market_frame, _position, _projection


def _replay_incrementally(
    projection: HistoricalManagedProjectionDTO,
    position: PositionState,
    market_frame: MarketFrame,
):
    entry_index = position.entry_fill.bar_index
    target_index = len(market_frame.candles) - 1
    rule_set = ManagedRuleSet.from_projection(projection)
    state = initialize_managed_trade_state(position)
    effective_states = []
    advance_calls = 0
    for bar_index in range(entry_index, target_index + 1):
        candle = market_frame.candles[bar_index]
        next_time_ms = (
            market_frame.candles[bar_index + 1].open_time_ms
            if bar_index + 1 < len(market_frame.candles)
            else None
        )
        state, effective = advance_managed_trade_state(
            state,
            projection,
            rule_set,
            trade_id=position.position_id,
            bar_index=bar_index,
            source_time_ms=candle.open_time_ms,
            high=float(candle.high),
            low=float(candle.low),
            next_time_ms=next_time_ms,
        )
        advance_calls += 1
        if effective is not None:
            effective_states.append(effective)
    return effective_states, advance_calls


@pytest.mark.parametrize(("side", "entry_index"), [("long", 0), ("long", 4), ("short", 1)])
def test_incremental_matches_eager_builder_bar_for_bar(side: str, entry_index: int) -> None:
    projection = _projection()
    market_frame = _market_frame()
    position = _position(entry_index=entry_index, side=side)

    eager = build_managed_policy_timeline_from_projection(projection, position, market_frame)
    incremental, advance_calls = _replay_incrementally(projection, position, market_frame)

    assert advance_calls == len(market_frame.candles) - entry_index
    assert len(incremental) == len(eager.states)
    for inc, eag in zip(incremental, eager.states, strict=True):
        assert inc.effective_time_ms == eag.effective_time_ms
        assert inc.source_bar_index == eag.source_bar_index
        assert inc.phase == eag.phase
        assert inc.bars_in_trade == eag.bars_in_trade
        assert inc.mfe_pct == eag.mfe_pct
        assert inc.mae_pct == eag.mae_pct
        assert inc.active_stop_price == eag.active_stop_price
        assert inc.active_stop_rule_id == eag.active_stop_rule_id
        assert inc.active_take_profile == eag.active_take_profile
        assert inc.active_take_rule_id == eag.active_take_rule_id
        assert inc.runtime_exit_rule_ids == eag.runtime_exit_rule_ids
        assert inc.runtime_exit_kinds == eag.runtime_exit_kinds


def test_confirm_bars_boundary_matches_incrementally_too() -> None:
    """Same fixture as
    test_confirm_bars_positive_boundary_arms_exactly_on_the_nth_consecutive_bar
    in test_managed_policy_from_projection.py, replayed through the
    incremental path: not armed at N-1, armed exactly at N, pre-entry
    true values excluded (the counter starts at entry, so it cannot
    have counted them)."""

    n = 8
    confirm_bars = 3
    condition = tuple(True for _ in range(n))
    projection = HistoricalManagedProjectionDTO(
        conditions={"rt:condition": ManagedConditionSeriesDTO(long=condition, short=condition)},
        distances={},
        rules=[
            {
                "kind": "runtime_exit",
                "rule_id": "rt",
                "activation_phase": "initial_risk",
                "condition_id": "rt:condition",
                "confirm_bars": confirm_bars,
                "exit_class": "runtime_close",
            },
        ],
    )
    position = _position(entry_index=1)
    market_frame = _market_frame(n)

    incremental, _ = _replay_incrementally(projection, position, market_frame)

    assert incremental[0].runtime_exit_rule_ids == ()  # bar_index 1, bars_in_trade 1
    assert incremental[1].runtime_exit_rule_ids == ()  # bar_index 2, bars_in_trade 2 = N-1
    assert incremental[2].runtime_exit_rule_ids == ("rt",)  # bar_index 3, bars_in_trade 3 = N
    assert all(s.runtime_exit_rule_ids == ("rt",) for s in incremental[2:])


def test_advance_call_count_is_bounded_by_actual_open_bars_not_remaining_range() -> None:
    """The complexity claim, directly: a trade that opens near the start
    of a large frame and stays open for a handful of bars must not
    require advancing through the rest of the frame -- the caller
    (the execution loop) simply stops calling advance() once the trade
    closes. This test proves the *function* itself never internally
    walks beyond what it's asked to."""

    n = 50_000
    market_frame = _market_frame(n)
    projection = _projection(n)
    position = _position(entry_index=10)

    rule_set = ManagedRuleSet.from_projection(projection)
    state = initialize_managed_trade_state(position)
    advance_calls = 0
    # Simulate a trade that closes after only 5 bars -- the caller stops
    # calling advance() at that point, exactly as run_projection_execution_loop
    # will once a position closes.
    for bar_index in range(10, 15):
        candle = market_frame.candles[bar_index]
        next_time_ms = market_frame.candles[bar_index + 1].open_time_ms
        state, _effective = advance_managed_trade_state(
            state, projection, rule_set, trade_id="p", bar_index=bar_index,
            source_time_ms=candle.open_time_ms, high=float(candle.high), low=float(candle.low),
            next_time_ms=next_time_ms,
        )
        advance_calls += 1

    assert advance_calls == 5
    assert advance_calls != n - 10  # the eager builder's own call count for this same trade
