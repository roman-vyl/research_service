from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    Candle,
    ManagedBarDecision,
    ManagedReplayResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    EntryFill,
    InitialProtection,
    PositionState,
)
from research_service.execution.managed_policy import (
    build_managed_policy_timeline,
    collect_managed_exit_candidates,
)


def position(side: str = "long") -> PositionState:
    return PositionState(
        position_id="trade-1",
        instance_id="instance-1",
        side=side,
        entry_fill=EntryFill(
            fill_id="entry-1",
            instance_id="instance-1",
            side=side,
            bar_index=0,
            time_ms=0,
            reference_price=Decimal("100"),
            fill_price=Decimal("100"),
            quantity=Decimal("1"),
            slippage_rate=Decimal("0"),
        ),
        initial_protection=InitialProtection(
            side=side,
            source_bar_index=0,
            source_time_ms=0,
            anchor_price=Decimal("100"),
            stop_loss_ratio=Decimal("0.02"),
            take_profit_ratio=Decimal("0.05"),
            stop_loss_price=Decimal("98") if side == "long" else Decimal("102"),
            take_profit_price=Decimal("105") if side == "long" else Decimal("95"),
        ),
    )


def replay(side: str = "long") -> ManagedReplayResult:
    return ManagedReplayResult(
        contract_version="managed_policy_replay.v1",
        decision_timing="end_of_bar_effective_next_bar",
        trade_id="trade-1",
        side=side,
        entry_time_ms=0,
        bars=(
            ManagedBarDecision(
                time_ms=0,
                bar_index=0,
                phase="protected",
                bars_in_trade=1,
                mfe_pct=Decimal("0.01"),
                mae_pct=Decimal("0.005"),
                active_stop_price=Decimal("100.5") if side == "long" else Decimal("99.5"),
                active_take_profile="disable_initial_tp",
                runtime_exit_rule_ids=("exit-1",),
                effective_from_time_ms=300_000,
            ),
            ManagedBarDecision(
                time_ms=300_000,
                bar_index=1,
                phase="protected",
                bars_in_trade=2,
                mfe_pct=Decimal("0.02"),
                mae_pct=Decimal("0.005"),
                active_stop_price=Decimal("100.5") if side == "long" else Decimal("99.5"),
                active_take_profile="disable_initial_tp",
                runtime_exit_rule_ids=(),
                effective_from_time_ms=None,
            ),
        ),
        events=(
            {
                "time_ms": 0,
                "bar_index": 0,
                "event_type": "active_stop_updated",
                "rule_id": "be",
                "component_id": "break_even_stop",
                "price": "100.5",
                "metadata": {"effective_from_bar": 1},
            },
            {
                "time_ms": 0,
                "bar_index": 0,
                "event_type": "active_take_updated",
                "rule_id": "disable-tp",
                "component_id": "take_profile_switch",
                "metadata": {
                    "take_profile": "disable_initial_tp",
                    "effective_from_bar": 1,
                },
            },
            {
                "time_ms": 0,
                "bar_index": 0,
                "event_type": "runtime_exit_triggered",
                "rule_id": "exit-1",
                "component_id": "phase_runtime_exit",
                "price": "101",
                "metadata": {"exit_kind": "market_close", "effective_from_bar": 1},
            },
        ),
        final_state={},
        raw={},
    )


def test_end_of_bar_policy_is_shifted_to_next_bar() -> None:
    timeline = build_managed_policy_timeline(replay(), position())
    assert timeline.state_for_time(0) is None
    state = timeline.state_for_time(300_000)
    assert state is not None
    assert state.source_bar_index == 0
    assert state.active_stop_rule_id == "be"
    assert state.active_stop_component_id == "break_even_stop"
    assert state.active_take_profile == "disable_initial_tp"
    assert state.active_take_rule_id == "disable-tp"
    assert state.runtime_exit_rule_ids == ("exit-1",)
    assert state.runtime_exit_kinds == {"exit-1": "market_close"}


def test_managed_stop_and_runtime_exit_become_execution_candidates() -> None:
    state = build_managed_policy_timeline(replay(), position()).state_for_time(300_000)
    assert state is not None
    candle = Candle(
        open_time_ms=300_000,
        open="101",
        high="102",
        low="100",
        close="101.5",
        volume="1",
    )
    candidates = collect_managed_exit_candidates(position(), candle, state, bar_index=1)
    assert [candidate.candidate_type for candidate in candidates] == [
        "managed_stop",
        "runtime_close",
    ]
    assert candidates[0].fill_price == Decimal("100.5")
    assert candidates[0].rule_id == "be"
    assert candidates[1].fill_price == Decimal("101.5")
    assert candidates[1].rule_id == "exit-1"


def test_managed_stop_gap_uses_bar_open_for_long_and_short() -> None:
    long_state = build_managed_policy_timeline(replay(), position()).state_for_time(300_000)
    assert long_state is not None
    long_candidates = collect_managed_exit_candidates(
        position(),
        Candle(open_time_ms=300_000, open="99", high="101", low="98", close="100", volume="1"),
        long_state,
        bar_index=1,
    )
    assert long_candidates[0].fill_price == Decimal("99")

    short_position = position("short")
    short_state = build_managed_policy_timeline(replay("short"), short_position).state_for_time(
        300_000
    )
    assert short_state is not None
    short_candidates = collect_managed_exit_candidates(
        short_position,
        Candle(open_time_ms=300_000, open="101", high="102", low="99", close="100", volume="1"),
        short_state,
        bar_index=1,
    )
    assert short_candidates[0].fill_price == Decimal("101")


def test_policy_is_not_recalculated_or_applied_on_source_bar() -> None:
    timeline = build_managed_policy_timeline(replay(), position())
    candle = Candle(open_time_ms=0, open="100", high="101", low="99", close="100", volume="1")
    assert (
        collect_managed_exit_candidates(position(), candle, timeline.state_for_time(0), bar_index=0)
        == ()
    )


def test_replay_identity_must_match_position() -> None:
    wrong = replay().model_copy(update={"trade_id": "other"})
    with pytest.raises(InvalidRequest):
        build_managed_policy_timeline(wrong, position())
