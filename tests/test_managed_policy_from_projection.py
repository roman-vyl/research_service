"""`build_managed_policy_timeline_from_projection` mechanics
(`historical-managed-projection-v1` tasks.md section 4). The formulas
themselves are parity-proven against `managed.py` on the Strategy Engine
side (`strategy_engine/tests/test_ema_pullback_historical_managed_projection.py`);
this test proves the Research-side generic consumer's own algorithm --
phase advancement, stop ratchet, take switch, entry-anchored confirm-bars
-- against a hand-computed trace, independent of that other repo/venv.
"""

from __future__ import annotations

from decimal import Decimal

from research_service.domain.contracts import (
    Candle,
    HistoricalManagedProjectionDTO,
    ManagedConditionSeriesDTO,
    MarketFrame,
    MarketRange,
)
from research_service.domain.execution import EntryFill, InitialProtection, PositionState
from research_service.execution.managed_policy import build_managed_policy_timeline_from_projection


def _position(*, entry_index: int, side: str = "long") -> PositionState:
    return PositionState(
        position_id="trade-1",
        instance_id="instance-1",
        side=side,
        entry_fill=EntryFill(
            fill_id="entry-1",
            instance_id="instance-1",
            side=side,
            bar_index=entry_index,
            time_ms=entry_index * 300_000,
            reference_price=Decimal("100"),
            fill_price=Decimal("100"),
            quantity=Decimal("1"),
            slippage_rate=Decimal("0"),
        ),
        initial_protection=InitialProtection(
            side=side,
            source_bar_index=entry_index,
            source_time_ms=entry_index * 300_000,
            anchor_price=Decimal("100"),
            stop_loss_ratio=Decimal("0.02"),
            take_profit_ratio=Decimal("0.05"),
            stop_loss_price=Decimal("98") if side == "long" else Decimal("102"),
            take_profit_price=Decimal("105") if side == "long" else Decimal("95"),
        ),
    )


def _market_frame(n: int = 6) -> MarketFrame:
    candles = tuple(
        Candle(
            open_time_ms=i * 300_000,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(n)
    )
    return MarketFrame(
        market=MarketRange(
            ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=n * 300_000
        ),
        candles=candles,
    )


def _projection(n: int = 6) -> HistoricalManagedProjectionDTO:
    # to-runner condition: true from bar_index 3 onward, both sides.
    runner_condition = tuple(i >= 3 for i in range(n))
    # runtime rule condition: true only at bar_index 4 and 5.
    runtime_condition = tuple(i in (4, 5) for i in range(n))
    return HistoricalManagedProjectionDTO(
        conditions={
            "to-runner:condition": ManagedConditionSeriesDTO(
                long=runner_condition, short=runner_condition
            ),
            "rt1:condition": ManagedConditionSeriesDTO(
                long=runtime_condition, short=runtime_condition
            ),
        },
        distances={
            "to-protected:distance": tuple(2.0 for _ in range(n)),
            "be:distance": tuple(0.5 for _ in range(n)),
            "lock:distance": tuple(1.0 for _ in range(n)),
        },
        rules=[
            {
                "kind": "phase_transition",
                "rule_id": "to-protected",
                "target_phase": "protected",
                "condition_id": None,
                "distance_id": "to-protected:distance",
                "trade_metric": "bars_since_entry",
            },
            {
                "kind": "phase_transition",
                "rule_id": "to-runner",
                "target_phase": "runner",
                "condition_id": "to-runner:condition",
                "distance_id": None,
                "trade_metric": None,
            },
            {
                "kind": "stop_action",
                "rule_id": "be",
                "activation_phase": "protected",
                "distance_id": "be:distance",
            },
            {
                "kind": "stop_action",
                "rule_id": "lock",
                "activation_phase": "runner",
                "distance_id": "lock:distance",
            },
            {
                "kind": "take_action",
                "rule_id": "disable-tp",
                "activation_phase": "runner",
                "resulting_profile": "disable_initial_tp",
            },
            {
                "kind": "runtime_exit",
                "rule_id": "rt1",
                "activation_phase": "initial_risk",
                "condition_id": "rt1:condition",
                "confirm_bars": 2,
                "exit_class": "runtime_close",
            },
        ],
    )


def test_phase_stop_take_mechanics_match_hand_computed_trace() -> None:
    timeline = build_managed_policy_timeline_from_projection(
        _projection(), _position(entry_index=0), _market_frame()
    )
    # bar 5 is the last bar -- never shifted onto a next bar, so only
    # bars 0..4 produce an effective state (5 states).
    assert len(timeline.states) == 5

    expected = [
        ("initial_risk", None, "initial", ()),
        ("protected", Decimal("100.5"), "initial", ()),
        ("protected", Decimal("100.5"), "initial", ()),
        ("runner", Decimal("101.0"), "disable_initial_tp", ()),
        ("runner", Decimal("101.0"), "disable_initial_tp", ()),
    ]
    for state, (phase, stop, take, runtime_ids) in zip(timeline.states, expected, strict=True):
        assert state.phase == phase, state
        assert state.active_stop_price == stop, state
        assert state.active_take_profile == take, state
        assert state.runtime_exit_rule_ids == runtime_ids, state

    # effective_time_ms is always the *next* bar's open time (end-of-bar
    # decision, effective next bar).
    assert [s.effective_time_ms for s in timeline.states] == [
        300_000,
        600_000,
        900_000,
        1_200_000,
        1_500_000,
    ]
    # Stop ratchets from break-even (0.5) to the tighter lock (1.0) once
    # runner is reached, attributed to the rule that produced it.
    assert timeline.states[1].active_stop_rule_id == "be"
    assert timeline.states[3].active_stop_rule_id == "lock"
    # component_id is never populated by the projection-driven path --
    # not part of this contract (design.md D2/D6).
    assert all(s.active_stop_component_id is None for s in timeline.states)
    assert all(s.active_take_component_id is None for s in timeline.states)


def test_runtime_confirm_bars_is_entry_anchored() -> None:
    """The runtime condition is true at bar_index 4 and 5 with
    confirm_bars=2 -- a trade entering at bar_index 0 has both bars
    inside its evaluation window and the state at bar_index 4 does NOT
    yet arm (window [3,4] has a False at 3); a trade entering at
    bar_index 4 starts its own window there, so by bar_index 5 (not
    shifted, so unobservable in states) the arming would use a
    different anchor -- this test confirms entry_index, not a shared
    candidate-wide series, gates the window's lower bound."""

    late_entry_timeline = build_managed_policy_timeline_from_projection(
        _projection(), _position(entry_index=4), _market_frame()
    )
    # Only bar_index 4 produces a state (5 is last bar, dropped); with
    # entry_index=4, start = 4 - 2 + 1 = 3 < entry_index(4) -> the
    # window is rejected for not being fully inside the trade's life,
    # exactly like managed.py's `_runtime_signal` entry-anchoring.
    assert len(late_entry_timeline.states) == 1
    assert late_entry_timeline.states[0].runtime_exit_rule_ids == ()

    early_entry_timeline = build_managed_policy_timeline_from_projection(
        _projection(), _position(entry_index=0), _market_frame()
    )
    # Same rule, same underlying condition series, different entry ->
    # its own bar_index 4 state also does not arm (window [3,4] fails
    # on the False at 3) -- but for a different reason (condition, not
    # anchoring), proving these two trades evaluate independently.
    assert early_entry_timeline.states[4].runtime_exit_rule_ids == ()


def test_confirm_bars_positive_boundary_arms_exactly_on_the_nth_consecutive_bar() -> None:
    """Precise positive-boundary case for confirm_bars=N=3, isolated to a
    single runtime_exit rule (no phase/stop/take rules, so nothing else
    can influence arming): the underlying condition is true starting
    one bar *before* entry and stays true through the end.

    entry_index=1, condition true at bar_index 0..7:
    - bar_index 2 (bars_in_trade=2=N-1): window would be [0,2] --
      3 consecutive true values exist, but bar 0 is pre-entry, so the
      entry-anchored window [1,2] (only 2 bars) is what's actually
      available -> NOT armed. This is also the "pre-entry true values
      don't count" case: if they did, this bar would incorrectly arm.
    - bar_index 3 (bars_in_trade=3=N): window [1,3] is fully inside
      the trade's life and all three bars are true -> armed, exactly
      on the Nth confirmed bar, not before.
    """

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
    timeline = build_managed_policy_timeline_from_projection(
        projection, _position(entry_index=1), _market_frame(n)
    )

    # states[k] corresponds to bar_index = entry_index + k = 1 + k.
    assert timeline.states[0].runtime_exit_rule_ids == ()  # bar_index 1, bars_in_trade 1
    assert timeline.states[1].runtime_exit_rule_ids == ()  # bar_index 2, bars_in_trade 2 = N-1
    assert timeline.states[2].runtime_exit_rule_ids == ("rt",)  # bar_index 3, bars_in_trade 3 = N
    # Stays armed on every later bar too (condition never goes false again).
    assert all(s.runtime_exit_rule_ids == ("rt",) for s in timeline.states[2:])

    # Next-bar effective timing is unchanged by any of this: the bar_index
    # 3 arming is effective starting at bar_index 4's open time.
    assert timeline.states[2].source_bar_index == 3
    assert timeline.states[2].effective_time_ms == 4 * 300_000
