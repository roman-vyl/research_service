from __future__ import annotations

from decimal import Decimal

from research_service.accounting import AccountingPolicy, account_execution_loop
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
    *, side: str = "long", entries: tuple[bool, ...] | None = None
) -> StrategyEvaluationResult:
    market = frame().market
    long_entries = entries or ((True, False, False, False) if side == "long" else (False,) * 4)
    short_entries = (True, False, False, False) if side == "short" else (False,) * 4
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="instance-1",
        config_hash="hash",
        market=market,
        bar_count=4,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000, 900_000),
        entries={"long": long_entries, "short": short_entries},
        exit_policy={
            "signal_exit": {"long": [False] * 4, "short": [False] * 4},
            "stop_loss_ratio": {"long": ["0.10"] * 4, "short": ["0.10"] * 4},
            "take_profit_ratio": {"long": ["0.05"] * 4, "short": ["0.05"] * 4},
            "stop_ready": {"long": [True] * 4, "short": [True] * 4},
        },
        component_evidence={},
        raw={},
    )


def test_long_trade_fees_pnl_equity_and_path() -> None:
    execution = run_unified_execution_loop(
        evaluation(),
        frame(),
        ExecutionPolicy(quantity=Decimal("2")),
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
    assert trade.entry_price == Decimal("100")
    assert trade.exit_price == Decimal("105.00")
    assert trade.gross_pnl == Decimal("10.00")
    assert trade.entry_fee == Decimal("0.200")
    assert trade.exit_fee == Decimal("0.21000")
    assert trade.net_pnl == Decimal("9.59000")
    assert trade.equity_after == Decimal("1009.59000")
    assert trade.path.mfe_price == Decimal("6")
    assert trade.path.mae_price == Decimal("2")
    assert trade.path.capture_ratio == Decimal("5") / Decimal("6")
    assert trade.path.giveback_price == Decimal("1.00")
    assert result.final_equity == trade.equity_after


def test_short_trade_uses_inverse_price_direction() -> None:
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
        evaluation(side="short"),
        custom,
        ExecutionPolicy(quantity=Decimal("3")),
    )
    result = account_execution_loop(
        execution, custom, AccountingPolicy(initial_equity=Decimal("500"))
    )
    trade = result.trades[0]
    assert trade.side == "short"
    assert trade.entry_price == Decimal("100")
    assert trade.exit_price == Decimal("95.00")
    assert trade.gross_pnl == Decimal("15.00")
    assert trade.path.mfe_price == Decimal("6")
    assert trade.path.mae_price == Decimal("2")


def test_open_position_is_not_realised() -> None:
    execution = run_unified_execution_loop(
        evaluation(entries=(False, False, True, False)),
        frame(),
        ExecutionPolicy(),
    )
    result = account_execution_loop(
        execution, frame(), AccountingPolicy(initial_equity=Decimal("1000"))
    )
    assert result.realised_trade_count == 0
    assert result.open_position_count == 1
    assert result.trades == ()
    assert result.final_equity == Decimal("1000")
    assert result.net_pnl == Decimal("0")


def test_multiple_trades_compound_equity_additively() -> None:
    custom_eval = evaluation(entries=(True, False, True, False))
    execution = run_unified_execution_loop(custom_eval, frame(), ExecutionPolicy())
    result = account_execution_loop(
        execution, frame(), AccountingPolicy(initial_equity=Decimal("1000"))
    )
    assert result.realised_trade_count == 1
    assert result.open_position_count == 1
    assert result.final_equity == Decimal("1005.00")
