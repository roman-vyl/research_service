from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    Candle,
    MarketFrame,
    MarketRange,
    StrategyEvaluationResult,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.entry import entry_decision_at, execute_entry, try_open_position


def _market() -> MarketFrame:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=900_000)
    return MarketFrame(
        market=market,
        candles=(
            Candle(open_time_ms=0, open="99", high="102", low="98", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="100", high="104", low="99", close="103", volume="1"),
            Candle(
                open_time_ms=600_000, open="103", high="105", low="101", close="102", volume="1"
            ),
        ),
    )


def _evaluation(
    *,
    long: tuple[bool, ...],
    short: tuple[bool, ...],
    long_ready: tuple[bool, ...] = (True, True, True),
    short_ready: tuple[bool, ...] = (True, True, True),
) -> StrategyEvaluationResult:
    market = _market().market
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="instance-1",
        config_hash="config-hash",
        market=market,
        bar_count=3,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000),
        entries={"long": long, "short": short},
        exit_policy={
            "signal_exit": {"long": [False] * 3, "short": [False] * 3},
            "stop_loss_ratio": {
                "long": ["0.01"] * 3,
                "short": ["0.01"] * 3,
            },
            "take_profit_ratio": {
                "long": ["0.03"] * 3,
                "short": ["0.03"] * 3,
            },
            "stop_ready": {
                "long": list(long_ready),
                "short": list(short_ready),
            },
        },
        component_evidence={},
        raw={},
    )


def test_long_entry_uses_signal_bar_close_and_initial_protection() -> None:
    market = _market()
    evaluation = _evaluation(long=(False, True, False), short=(False, False, False))

    position = try_open_position(
        evaluation,
        market,
        ExecutionPolicy(),
        bar_index=1,
        current_position=None,
    )

    assert position is not None
    assert position.side == "long"
    assert position.entry_fill.time_ms == 300_000
    assert position.entry_fill.reference_price == Decimal("103")
    assert position.entry_fill.fill_price == Decimal("103")
    assert position.initial_protection.stop_loss_price == Decimal("101.97")
    assert position.initial_protection.take_profit_price == Decimal("106.09")


def test_short_entry_uses_signal_bar_close() -> None:
    market = _market()
    evaluation = _evaluation(long=(False, False, False), short=(False, True, False))

    decision = entry_decision_at(evaluation, market, bar_index=1)

    assert decision is not None
    assert decision.side == "short"
    assert decision.reference_price == Decimal("103")


def test_long_has_deterministic_priority_when_both_sides_signal_and_ready() -> None:
    decision = entry_decision_at(
        _evaluation(long=(True, False, False), short=(True, False, False)),
        _market(),
        bar_index=0,
    )
    assert decision is not None
    assert decision.side == "long"


def test_ready_short_can_open_when_long_signal_is_not_ready() -> None:
    decision = entry_decision_at(
        _evaluation(
            long=(True, False, False),
            short=(True, False, False),
            long_ready=(False, True, True),
        ),
        _market(),
        bar_index=0,
    )
    assert decision is not None
    assert decision.side == "short"


def test_unready_entry_is_filtered_like_legacy_entries_and_stop_ready() -> None:
    assert (
        entry_decision_at(
            _evaluation(
                long=(False, True, False),
                short=(False, False, False),
                long_ready=(True, False, True),
            ),
            _market(),
            bar_index=1,
        )
        is None
    )


def test_existing_position_blocks_reentry() -> None:
    market = _market()
    evaluation = _evaluation(long=(True, True, False), short=(False, False, False))
    policy = ExecutionPolicy()
    first = try_open_position(evaluation, market, policy, bar_index=0, current_position=None)
    assert first is not None

    second = try_open_position(evaluation, market, policy, bar_index=1, current_position=first)

    assert second is first


def test_no_signal_does_not_open_position() -> None:
    assert (
        try_open_position(
            _evaluation(long=(False, False, False), short=(False, False, False)),
            _market(),
            ExecutionPolicy(),
            bar_index=2,
            current_position=None,
        )
        is None
    )


@pytest.mark.parametrize(
    ("side", "expected"),
    [("long", Decimal("101.00")), ("short", Decimal("99.00"))],
)
def test_entry_slippage_is_adverse_and_side_aware(side: str, expected: Decimal) -> None:
    evaluation = _evaluation(
        long=(side == "long", False, False),
        short=(side == "short", False, False),
    )
    decision = entry_decision_at(evaluation, _market(), bar_index=0)
    assert decision is not None

    fill = execute_entry(
        decision,
        ExecutionPolicy(entry_slippage_rate=Decimal("0.01")),
    )

    assert fill.fill_price == expected
