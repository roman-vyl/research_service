"""Trade-native R accounting (`research-trade-native-r-v1`).

Denominator is frozen at entry -- |entry fill price - initial stop price| --
independent of exit path (managed/signal/runtime), independent of quantity
and portfolio sizing. See `accounting/service.py::_initial_risk` and
`accounting/contracts.py::TradeRecord`'s R fields.
"""

from __future__ import annotations

from decimal import Decimal

from research_service.accounting import AccountingPolicy, account_execution_loop
from research_service.application.experiments.candidate_summary import (
    derive_batch_candidate_summary,
)
from research_service.domain.contracts import (
    Candle,
    MarketFrame,
    MarketRange,
    StrategyEvaluationResult,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.loop import run_unified_execution_loop


def frame() -> MarketFrame:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=1_200_000)
    return MarketFrame(
        market=market,
        candles=(
            Candle(open_time_ms=0, open="99", high="102", low="98", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="100", high="106", low="99", close="105", volume="1"),
            Candle(
                open_time_ms=600_000, open="105", high="106", low="101", close="102", volume="1"
            ),
            Candle(open_time_ms=900_000, open="102", high="103", low="99", close="100", volume="1"),
        ),
    )


def evaluation(
    *,
    side: str = "long",
    entries: tuple[bool, ...] | None = None,
    stop_loss_ratio: str | None = "0.10",
) -> StrategyEvaluationResult:
    market = frame().market
    long_entries = entries or ((True, False, False, False) if side == "long" else (False,) * 4)
    short_entries = (True, False, False, False) if side == "short" else (False,) * 4
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id="instance-1",
        config_hash="hash",
        market=market,
        bar_count=4,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000, 900_000),
        entries={"long": long_entries, "short": short_entries},
        exit_policy={
            "signal_exit": {"long": [False] * 4, "short": [False] * 4},
            "stop_loss_ratio": {"long": [stop_loss_ratio] * 4, "short": [stop_loss_ratio] * 4},
            "take_profit_ratio": {"long": ["0.05"] * 4, "short": ["0.05"] * 4},
            "stop_ready": {"long": [True] * 4, "short": [True] * 4},
        },
        component_evidence={},
        raw={},
    )


# --- 1. correct R for long/short -------------------------------------------


def test_correct_gross_and_net_r_for_long() -> None:
    # entry=100, stop_loss_ratio=0.10 -> stop=90, initial_risk_price=10.
    # quantity=2 -> initial_risk_amount=20. exit=105 -> gross=10.00 -> R=0.5.
    execution = run_unified_execution_loop(
        evaluation(), frame(), ExecutionPolicy(), quantity=Decimal("2")
    )
    result = account_execution_loop(
        execution,
        frame(),
        AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
    )
    trade = result.trades[0]
    assert trade.initial_risk_price == Decimal("10")
    assert trade.initial_risk_amount == Decimal("20")
    assert trade.gross_r_multiple == Decimal("0.5")
    assert trade.net_r_multiple == trade.net_pnl / Decimal("20")


def test_correct_gross_and_net_r_for_short() -> None:
    # entry=100, stop_loss_ratio=0.10 -> stop=110, initial_risk_price=10.
    # quantity=3 -> initial_risk_amount=30. exit=95 -> gross=15.00 -> R=0.5.
    custom = frame().model_copy(
        update={
            "candles": (
                frame().candles[0],
                Candle(
                    open_time_ms=300_000, open="100", high="101", low="94", close="95", volume="1"
                ),
                *frame().candles[2:],
            )
        }
    )
    execution = run_unified_execution_loop(
        evaluation(side="short"), custom, ExecutionPolicy(), quantity=Decimal("3")
    )
    result = account_execution_loop(
        execution, custom, AccountingPolicy(initial_equity=Decimal("500"))
    )
    trade = result.trades[0]
    assert trade.side == "short"
    assert trade.initial_risk_price == Decimal("10")
    assert trade.initial_risk_amount == Decimal("30")
    assert trade.gross_r_multiple == Decimal("0.5")
    assert trade.net_r_multiple == Decimal("0.5")  # zero fees here


# --- 2. R invariant to quantity ---------------------------------------------


def test_r_multiple_is_invariant_to_quantity() -> None:
    r_multiples = []
    for quantity in (Decimal("1"), Decimal("2"), Decimal("50"), Decimal("0.001")):
        execution = run_unified_execution_loop(
            evaluation(), frame(), ExecutionPolicy(), quantity=quantity
        )
        result = account_execution_loop(
            execution, frame(), AccountingPolicy(initial_equity=Decimal("100000"))
        )
        trade = result.trades[0]
        r_multiples.append(trade.gross_r_multiple)
    assert len(set(r_multiples)) == 1
    assert r_multiples[0] == Decimal("0.5")


# --- 3. fractional R when exit is not on the initial SL/TP level -----------


def test_fractional_r_when_exit_is_not_on_initial_sl_or_tp() -> None:
    # entry=100, stop=90, take=105 (0.10/0.05 ratios). bar1 stays strictly
    # inside that band (high=103, low=97) so neither SL nor TP fires there;
    # a signal exit instead closes at bar1's close (102) -- gross=2.00 on a
    # 10-wide initial risk -> R=0.2, a genuinely fractional multiple.
    inside_band_frame = frame().model_copy(
        update={
            "candles": (
                frame().candles[0],
                Candle(
                    open_time_ms=300_000, open="100", high="103", low="97", close="102", volume="1"
                ),
                *frame().candles[2:],
            )
        }
    )
    custom_eval = evaluation().model_copy(
        update={
            "exit_policy": {
                **evaluation().exit_policy,
                "signal_exit": {"long": [False, True, False, False], "short": [False] * 4},
            }
        }
    )
    execution = run_unified_execution_loop(
        custom_eval, inside_band_frame, ExecutionPolicy(), quantity=Decimal("1")
    )
    result = account_execution_loop(
        execution, inside_band_frame, AccountingPolicy(initial_equity=Decimal("1000"))
    )
    trade = result.trades[0]
    assert trade.exit_reason == "signal"
    assert trade.exit_price == Decimal("102")
    assert trade.gross_pnl == Decimal("2.00")
    assert trade.initial_risk_amount == Decimal("10")
    assert trade.gross_r_multiple == Decimal("0.2")


# --- 4. missing initial stop -> R fields None, trade still valid -----------


def test_missing_initial_stop_leaves_r_fields_none() -> None:
    execution = run_unified_execution_loop(
        evaluation(stop_loss_ratio=None), frame(), ExecutionPolicy(), quantity=Decimal("1")
    )
    result = account_execution_loop(
        execution, frame(), AccountingPolicy(initial_equity=Decimal("1000"))
    )
    trade = result.trades[0]
    assert trade.initial_risk_price is None
    assert trade.initial_risk_amount is None
    assert trade.gross_r_multiple is None
    assert trade.net_r_multiple is None
    # the trade itself remains fully valid -- equity/pnl unaffected.
    assert trade.net_pnl == Decimal("5.00")
    assert trade.equity_after == Decimal("1005.00")


# --- 5. gross/net R differ correctly with fees ------------------------------


def test_gross_and_net_r_differ_with_fees() -> None:
    execution = run_unified_execution_loop(
        evaluation(), frame(), ExecutionPolicy(), quantity=Decimal("2")
    )
    result = account_execution_loop(
        execution,
        frame(),
        AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
    )
    trade = result.trades[0]
    assert trade.fees_paid > 0
    assert trade.gross_r_multiple != trade.net_r_multiple
    assert trade.gross_r_multiple == trade.gross_pnl / trade.initial_risk_amount
    assert trade.net_r_multiple == trade.net_pnl / trade.initial_risk_amount
    assert trade.net_r_multiple < trade.gross_r_multiple  # fees only ever cost R on a winner


# --- 6. candidate cumulative R == sum of eligible TradeRecord R, incl. sides


def test_candidate_cumulative_r_matches_sum_of_eligible_trades_with_long_short_split() -> None:
    # bar0->bar1: long entry at 100, TP(105) hit at bar1 -> closes long.
    # bar2->bar3: short entry at 102 (flat after the long closed), TP(96.9)
    # hit at bar3 (low=94) -> closes short. Both trades realised in one run.
    two_trade_frame = frame().model_copy(
        update={
            "candles": (
                *frame().candles[:3],
                Candle(open_time_ms=900_000, open="97", high="97", low="94", close="96", volume="1"),
            )
        }
    )
    custom_eval = evaluation().model_copy(
        update={
            "entries": {"long": (True, False, False, False), "short": (False, False, True, False)},
        }
    )
    execution = run_unified_execution_loop(
        custom_eval, two_trade_frame, ExecutionPolicy(), quantity=Decimal("1")
    )
    accounting = account_execution_loop(
        execution, two_trade_frame, AccountingPolicy(initial_equity=Decimal("1000"))
    )
    assert accounting.realised_trade_count == 2
    summary = derive_batch_candidate_summary(accounting)

    eligible = [t for t in accounting.trades if t.gross_r_multiple is not None]
    assert summary.r_eligible_trade_count == len(eligible)
    assert summary.cumulative_gross_r == sum(
        (t.gross_r_multiple for t in eligible), Decimal("0")
    )
    assert summary.cumulative_net_r == sum((t.net_r_multiple for t in eligible), Decimal("0"))

    long_eligible = [t for t in eligible if t.side == "long"]
    short_eligible = [t for t in eligible if t.side == "short"]
    assert summary.long.r_eligible_trade_count == len(long_eligible)
    assert summary.short.r_eligible_trade_count == len(short_eligible)
    assert summary.long.cumulative_gross_r == sum(
        (t.gross_r_multiple for t in long_eligible), Decimal("0")
    )
    assert summary.short.cumulative_gross_r == sum(
        (t.gross_r_multiple for t in short_eligible), Decimal("0")
    )
    assert summary.cumulative_gross_r == (
        summary.long.cumulative_gross_r + summary.short.cumulative_gross_r
    )


def test_r_eligible_trade_count_zero_when_no_trades_have_initial_stop() -> None:
    custom_eval = evaluation(entries=(True, False, True, False), stop_loss_ratio=None)
    execution = run_unified_execution_loop(
        custom_eval, frame(), ExecutionPolicy(), quantity=Decimal("1")
    )
    accounting = account_execution_loop(
        execution, frame(), AccountingPolicy(initial_equity=Decimal("1000"))
    )
    summary = derive_batch_candidate_summary(accounting)
    assert summary.r_eligible_trade_count == 0
    assert summary.cumulative_gross_r == Decimal("0")
    assert summary.cumulative_net_r == Decimal("0")
