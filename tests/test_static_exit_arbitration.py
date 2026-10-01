from decimal import Decimal

import pytest

from research_service.domain.contracts import Candle, MarketRange, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import EntryFill, InitialProtection, PositionState
from research_service.execution.static_exits import (
    _distance_fill_price,
    arbitrate_static_exit_candidates,
    collect_static_exit_candidates,
    execute_static_exit,
)


def evaluation(*, signal_long=(False, False), signal_short=(False, False)):
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000)
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id="i1",
        config_hash="cfg",
        market=market,
        bar_count=2,
        market_data_hash="hash",
        time_ms=(0, 300_000),
        entries={"long": (True, False), "short": (False, False)},
        exit_policy={
            "signal_exit": {"long": list(signal_long), "short": list(signal_short)},
            "stop_loss_ratio": {"long": ["0.02", "0.02"], "short": ["0.02", "0.02"]},
            "take_profit_ratio": {"long": ["0.05", "0.05"], "short": ["0.05", "0.05"]},
            "stop_ready": {"long": [True, True], "short": [True, True]},
        },
        component_evidence={},
        raw={},
    )


def position(side="long"):
    fill = EntryFill(
        fill_id="entry",
        instance_id="i1",
        side=side,
        bar_index=0,
        time_ms=0,
        reference_price="100",
        fill_price="100",
        quantity="1",
        slippage_rate="0",
    )
    protection = InitialProtection(
        side=side,
        source_bar_index=0,
        source_time_ms=0,
        anchor_price="100",
        stop_loss_ratio="0.02",
        take_profit_ratio="0.05",
        stop_loss_price="98" if side == "long" else "102",
        take_profit_price="105" if side == "long" else "95",
    )
    return PositionState(
        position_id="p1",
        instance_id="i1",
        side=side,
        entry_fill=fill,
        initial_protection=protection,
    )


def candle(open_, high, low, close):
    return Candle(open_time_ms=300_000, open=open_, high=high, low=low, close=close, volume="1")


# research-static-exit-arbitration-v1 "Distance fill semantics"
# (research-frozen-partial-take-ladder-v1, design D8): continuous market,
# a level crossed by the bar open still fills at exactly the level.


def test_long_stop_gap_fills_at_level_not_open() -> None:
    candidates = collect_static_exit_candidates(
        evaluation(), position(), candle("97", "99", "96", "98"), bar_index=1
    )
    assert candidates[0].candidate_type == "stop_loss"
    assert candidates[0].fill_price == Decimal("98")


def test_long_take_gap_fills_at_level_not_open() -> None:
    candidates = collect_static_exit_candidates(
        evaluation(), position(), candle("106", "107", "104", "106"), bar_index=1
    )
    assert candidates[0].candidate_type == "take_profit"
    assert candidates[0].fill_price == Decimal("105")


def test_short_gap_fills_at_level_not_open() -> None:
    stop = collect_static_exit_candidates(
        evaluation(), position("short"), candle("103", "104", "101", "102"), bar_index=1
    )
    assert stop[0].candidate_type == "stop_loss"
    assert stop[0].fill_price == Decimal("102")

    take = collect_static_exit_candidates(
        evaluation(), position("short"), candle("94", "96", "93", "94.5"), bar_index=1
    )
    assert take[0].candidate_type == "take_profit"
    assert take[0].fill_price == Decimal("95")


@pytest.mark.parametrize(
    ("side", "is_loss", "level", "open_", "high", "low"),
    [
        ("long", False, "108", "112", "113", "111"),  # final 108, open 112 -> 108
        ("long", True, "95", "90", "91", "89"),  # stop 95, open 90 -> 95
        ("short", False, "92", "88", "89", "87"),  # final 92, open 88 -> 92
        ("short", True, "105", "110", "111", "109"),  # stop 105, open 110 -> 105
    ],
)
def test_gap_through_fills_at_the_frozen_level(side, is_loss, level, open_, high, low) -> None:
    price = _distance_fill_price(
        side, candle(open_, high, low, open_), level=Decimal(level), is_loss=is_loss
    )
    assert price == Decimal(level)


def test_whole_bar_beyond_the_level_fills_at_level() -> None:
    long_stop = collect_static_exit_candidates(
        evaluation(), position(), candle("90", "91", "89", "90"), bar_index=1
    )
    assert [(c.candidate_type, c.fill_price) for c in long_stop] == [
        ("stop_loss", Decimal("98"))
    ]
    long_take = collect_static_exit_candidates(
        evaluation(), position(), candle("112", "113", "111", "112"), bar_index=1
    )
    assert [(c.candidate_type, c.fill_price) for c in long_take] == [
        ("take_profit", Decimal("105"))
    ]
    short_stop = collect_static_exit_candidates(
        evaluation(), position("short"), candle("110", "111", "109", "110"), bar_index=1
    )
    assert [(c.candidate_type, c.fill_price) for c in short_stop] == [
        ("stop_loss", Decimal("102"))
    ]
    short_take = collect_static_exit_candidates(
        evaluation(), position("short"), candle("88", "89", "87", "88"), bar_index=1
    )
    assert [(c.candidate_type, c.fill_price) for c in short_take] == [
        ("take_profit", Decimal("95"))
    ]


def test_same_bar_priority_is_stop_then_take_then_signal() -> None:
    candidates = collect_static_exit_candidates(
        evaluation(signal_long=(False, True)),
        position(),
        candle("100", "106", "97", "103"),
        bar_index=1,
    )
    result = arbitrate_static_exit_candidates(candidates)
    assert result.winner is not None
    assert result.winner.candidate_type == "stop_loss"
    assert [c.candidate_type for c in result.losing_candidates] == ["take_profit", "signal"]


def test_signal_exit_fills_at_close() -> None:
    candidates = collect_static_exit_candidates(
        evaluation(signal_long=(False, True)),
        position(),
        candle("100", "102", "99", "101.25"),
        bar_index=1,
    )
    result = arbitrate_static_exit_candidates(candidates)
    fill = execute_static_exit(position(), result)
    assert fill is not None
    assert fill.candidate_type == "signal"
    assert fill.fill_price == Decimal("101.25")


def test_entry_bar_cannot_exit_in_same_bar() -> None:
    first = Candle(open_time_ms=0, open="100", high="110", low="90", close="100", volume="1")
    assert collect_static_exit_candidates(evaluation(), position(), first, bar_index=0) == ()


def test_timestamp_mismatch_is_rejected() -> None:
    bad = Candle(open_time_ms=0, open="100", high="101", low="99", close="100", volume="1")
    with pytest.raises(InvalidRequest, match="timestamp"):
        collect_static_exit_candidates(evaluation(), position(), bad, bar_index=1)
