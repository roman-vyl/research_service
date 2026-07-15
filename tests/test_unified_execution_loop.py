from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    Candle,
    ManagedBarDecision,
    ManagedReplayResult,
    MarketFrame,
    MarketRange,
    StrategyEvaluationResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionPolicy, PositionState
from research_service.execution.loop import run_unified_execution_loop


def market() -> MarketFrame:
    identity = MarketRange(
        ticker="BTCUSDT.P",
        timeframe="5m",
        from_ms=0,
        to_ms=1_200_000,
    )
    return MarketFrame(
        market=identity,
        candles=(
            Candle(
                open_time_ms=0,
                open="99",
                high="101",
                low="98",
                close="100",
                volume="1",
            ),
            Candle(
                open_time_ms=300_000,
                open="100",
                high="106",
                low="99",
                close="104",
                volume="1",
            ),
            Candle(
                open_time_ms=600_000,
                open="104",
                high="105",
                low="101",
                close="102",
                volume="1",
            ),
            Candle(
                open_time_ms=900_000,
                open="102",
                high="103",
                low="100",
                close="101",
                volume="1",
            ),
        ),
    )


def evaluation(
    *,
    long_entries: tuple[bool, ...] = (True, False, False, False),
    short_entries: tuple[bool, ...] = (False, False, False, False),
    signal_long: tuple[bool, ...] = (False, False, False, False),
    stop_ratio: str = "0.10",
    take_ratio: str = "0.05",
) -> StrategyEvaluationResult:
    identity = market().market
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="instance-1",
        config_hash="config-hash",
        market=identity,
        bar_count=4,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000, 900_000),
        entries={"long": long_entries, "short": short_entries},
        exit_policy={
            "signal_exit": {
                "long": list(signal_long),
                "short": [False] * 4,
            },
            "stop_loss_ratio": {
                "long": [stop_ratio] * 4,
                "short": [stop_ratio] * 4,
            },
            "take_profit_ratio": {
                "long": [take_ratio] * 4,
                "short": [take_ratio] * 4,
            },
            "stop_ready": {
                "long": [True] * 4,
                "short": [True] * 4,
            },
        },
        component_evidence={},
        raw={},
    )


def managed_replay_for(position: PositionState) -> ManagedReplayResult:
    return ManagedReplayResult(
        contract_version="managed_policy_replay.v1",
        decision_timing="end_of_bar_effective_next_bar",
        trade_id=position.position_id,
        side=position.side,
        entry_time_ms=position.entry_fill.time_ms,
        bars=(
            ManagedBarDecision(
                time_ms=0,
                bar_index=0,
                phase="protected",
                bars_in_trade=1,
                mfe_pct=Decimal("0.01"),
                mae_pct=Decimal("0.005"),
                active_stop_price=Decimal("101"),
                active_take_profile="disable_initial_tp",
                runtime_exit_rule_ids=(),
                effective_from_time_ms=300_000,
            ),
            ManagedBarDecision(
                time_ms=300_000,
                bar_index=1,
                phase="protected",
                bars_in_trade=2,
                mfe_pct=Decimal("0.04"),
                mae_pct=Decimal("0.005"),
                active_stop_price=Decimal("101"),
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
        ),
        final_state={},
        raw={},
    )


def test_loop_opens_then_closes_on_static_take_profit() -> None:
    result = run_unified_execution_loop(
        evaluation(),
        market(),
        ExecutionPolicy(),
    )

    assert result.contract_version == "research_execution_loop.v1"
    assert len(result.positions) == 1
    execution = result.positions[0]
    assert execution.status == "closed"
    assert execution.position.entry_fill.bar_index == 0
    assert execution.exit_fill is not None
    assert execution.exit_fill.bar_index == 1
    assert execution.exit_fill.candidate_type == "take_profit"
    assert execution.exit_fill.fill_price == Decimal("105.00")
    assert [event.event_type for event in result.events] == [
        "entry_filled",
        "exit_filled",
    ]
    assert result.final_open_position is None


def test_position_open_at_bar_start_blocks_same_bar_reentry() -> None:
    result = run_unified_execution_loop(
        evaluation(long_entries=(True, True, True, False)),
        market(),
        ExecutionPolicy(),
    )

    assert [item.position.entry_fill.bar_index for item in result.positions] == [0, 2]
    assert result.positions[0].status == "closed"
    assert result.positions[1].status == "open"
    assert result.final_open_position is not None
    assert result.final_open_position.entry_fill.bar_index == 2
    assert [event.event_type for event in result.events] == [
        "entry_filled",
        "exit_filled",
        "entry_filled",
        "position_left_open",
    ]


def test_position_cannot_exit_on_its_entry_bar() -> None:
    custom = MarketFrame(
        market=market().market,
        candles=(
            Candle(
                open_time_ms=0,
                open="100",
                high="120",
                low="80",
                close="100",
                volume="1",
            ),
            *market().candles[1:],
        ),
    )
    result = run_unified_execution_loop(
        evaluation(take_ratio="0.01"),
        custom,
        ExecutionPolicy(),
    )

    assert result.positions[0].exit_fill is not None
    assert result.positions[0].exit_fill.bar_index == 1


def test_managed_replay_is_resolved_once_and_applied_on_next_bar() -> None:
    calls: list[str] = []

    def provider(position: PositionState) -> ManagedReplayResult:
        calls.append(position.position_id)
        return managed_replay_for(position)

    result = run_unified_execution_loop(
        evaluation(stop_ratio="0.20", take_ratio="0.20"),
        market(),
        ExecutionPolicy(),
        managed_replay_provider=provider,
    )

    assert calls == ["position:instance-1:long:0"]
    execution = result.positions[0]
    assert execution.status == "closed"
    assert execution.exit_fill is not None
    assert execution.exit_fill.candidate_type == "managed_stop"
    assert execution.exit_fill.bar_index == 1
    assert execution.exit_fill.fill_price == Decimal("100")
    assert execution.exit_fill.rule_id == "be"
    assert result.events[1].metadata["layer"] == "exit_management"


def test_invalid_managed_replay_identity_is_rejected() -> None:
    def provider(position: PositionState) -> ManagedReplayResult:
        return managed_replay_for(position).model_copy(update={"trade_id": "wrong"})

    with pytest.raises(InvalidRequest, match="another position"):
        run_unified_execution_loop(
            evaluation(stop_ratio="0.20", take_ratio="0.20"),
            market(),
            ExecutionPolicy(),
            managed_replay_provider=provider,
        )


def test_no_entries_produces_empty_result() -> None:
    result = run_unified_execution_loop(
        evaluation(long_entries=(False, False, False, False)),
        market(),
        ExecutionPolicy(),
    )
    assert result.positions == ()
    assert result.events == ()
    assert result.final_open_position is None


def test_grid_mismatch_is_rejected_before_iteration() -> None:
    wrong = evaluation().model_copy(
        update={
            "market": MarketRange(
                ticker="ETHUSDT.P",
                timeframe="5m",
                from_ms=0,
                to_ms=1_200_000,
            )
        }
    )
    with pytest.raises(InvalidRequest, match="market frame differ"):
        run_unified_execution_loop(wrong, market(), ExecutionPolicy())
