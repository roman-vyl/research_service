from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from research_service.accounting import AccountingPolicy, account_execution_loop
from research_service.accounting.contracts import TradeAccountingResult, TradePathMetrics, TradeRecord
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
        ExecutionPolicy(),
        quantity=Decimal("2"),
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
        ExecutionPolicy(),
        quantity=Decimal("3"),
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


def _path() -> TradePathMetrics:
    return TradePathMetrics(
        mfe_price=Decimal("1"),
        mfe_pct=Decimal("0.01"),
        mfe_bar_index=0,
        mfe_bars_from_entry=0,
        mae_price=Decimal("1"),
        mae_pct=Decimal("0.01"),
        mae_bar_index=0,
        mae_bars_from_entry=0,
        captured_price=Decimal("1"),
        captured_pct=Decimal("0.01"),
        bars_from_mfe_to_exit=0,
    )


def _chained_trade(
    *, ordinal: int, equity_before: Decimal, net_pnl: Decimal
) -> TradeRecord:
    """One valid, individually-consistent TradeRecord (fees zero, so
    gross_pnl == net_pnl) with a real Decimal-computed `equity_after` --
    `equity_before + net_pnl`, the same operation the accounting engine
    performs, not a hand-picked round number."""

    equity_after = equity_before + net_pnl
    return TradeRecord(
        trade_id=f"trade:{ordinal}",
        position_id=f"position:{ordinal}",
        instance_id="instance-1",
        side="long",
        entry_bar_index=ordinal,
        exit_bar_index=ordinal,
        entry_time_ms=ordinal * 300_000,
        exit_time_ms=ordinal * 300_000,
        entry_price=Decimal("100"),
        exit_price=Decimal("100"),
        quantity=Decimal("1"),
        entry_notional=Decimal("100"),
        exit_notional=Decimal("100"),
        gross_pnl=net_pnl,
        entry_fee=Decimal("0"),
        exit_fee=Decimal("0"),
        fees_paid=Decimal("0"),
        net_pnl=net_pnl,
        gross_return_pct=Decimal("0"),
        net_return_pct=Decimal("0"),
        equity_before=equity_before,
        equity_after=equity_after,
        hold_bars=1,
        hold_ms=300_000,
        exit_candidate_type="take_profit",
        exit_reason="take_profit",
        exit_layer="exit_policy",
        path=_path(),
    )


def _build_chain(*, initial_equity: Decimal, net_pnls: list[Decimal]) -> tuple[TradeRecord, ...]:
    """Real chained Decimal accumulation, exactly matching
    `account_execution_loop`'s own `equity = record.equity_after` loop --
    the mechanism this module's numerical-residue tolerance exists for."""

    trades = []
    equity = initial_equity
    for ordinal, net_pnl in enumerate(net_pnls, start=1):
        trade = _chained_trade(ordinal=ordinal, equity_before=equity, net_pnl=net_pnl)
        trades.append(trade)
        equity = trade.equity_after
    return tuple(trades)


def test_long_chain_numerical_residue_is_tolerated() -> None:
    """Regression: on a long trade sequence, the equity chain (each
    `equity_after = equity_before + net_pnl`) and the independent
    `sum(trade.net_pnl)` are two different Decimal accumulation paths over
    the same values -- they can diverge in the last few digits of the
    default 28-digit context purely from accumulated rounding (observed:
    ~1e-23 residue over ~1900 real trades; reproduced here with 50
    high-precision fractional trades, which is enough to trigger the same
    context-precision crowding). The equity chain itself must still be
    exactly continuous -- this is not a relaxation of that guarantee."""

    initial_equity = Decimal("10000")
    net_pnls = [Decimal("0.123456789012345678901234567") for _ in range(50)]
    trades = _build_chain(initial_equity=initial_equity, net_pnls=net_pnls)

    chain_final_equity = trades[-1].equity_after
    independent_sum = sum((t.net_pnl for t in trades), Decimal("0"))
    residue = abs(chain_final_equity - (initial_equity + independent_sum))
    assert residue > 0, "test setup must actually reproduce a nonzero residue"
    assert residue < Decimal("1e-10"), "residue must stay within the tolerated range"

    result = TradeAccountingResult(
        instance_id="instance-1",
        initial_equity=initial_equity,
        final_equity=chain_final_equity,
        realised_trade_count=len(trades),
        open_position_count=0,
        gross_pnl=independent_sum,
        fees_paid=Decimal("0"),
        net_pnl=independent_sum,
        trades=trades,
    )
    assert result.final_equity == chain_final_equity
    assert result.trades[-1].equity_after == result.final_equity


def test_equity_chain_break_still_fails_closed() -> None:
    """Negative control: a genuine equity discontinuity (not numerical
    residue) must still be rejected -- the tolerance introduced above must
    not paper over a real bookkeeping bug."""

    initial_equity = Decimal("10000")
    net_pnls = [Decimal("10"), Decimal("20"), Decimal("30")]
    trades = list(_build_chain(initial_equity=initial_equity, net_pnls=net_pnls))
    # Break the chain: the last trade's equity_before/equity_after both
    # shifted by a real $5 -- far larger than the numerical-residue
    # tolerance, and not internally self-consistent with the previous
    # trade's equity_after either.
    broken_before = trades[-1].equity_before + Decimal("5")
    trades[-1] = trades[-1].model_copy(
        update={"equity_before": broken_before, "equity_after": broken_before + trades[-1].net_pnl}
    )

    with pytest.raises(ValidationError, match="equity_before does not chain"):
        TradeAccountingResult(
            instance_id="instance-1",
            initial_equity=initial_equity,
            final_equity=trades[-1].equity_after,
            realised_trade_count=len(trades),
            open_position_count=0,
            gross_pnl=sum((t.net_pnl for t in trades), Decimal("0")),
            fees_paid=Decimal("0"),
            net_pnl=sum((t.net_pnl for t in trades), Decimal("0")),
            trades=tuple(trades),
        )


def test_final_equity_mismatch_beyond_tolerance_still_fails_closed() -> None:
    """Negative control: a `final_equity` that disagrees with the last
    trade's `equity_after` by a real amount (not numerical residue) must
    still be rejected."""

    initial_equity = Decimal("10000")
    net_pnls = [Decimal("10"), Decimal("20"), Decimal("30")]
    trades = _build_chain(initial_equity=initial_equity, net_pnls=net_pnls)

    with pytest.raises(ValidationError, match="final_equity differs from the last trade"):
        TradeAccountingResult(
            instance_id="instance-1",
            initial_equity=initial_equity,
            final_equity=trades[-1].equity_after + Decimal("1"),
            realised_trade_count=len(trades),
            open_position_count=0,
            gross_pnl=sum((t.net_pnl for t in trades), Decimal("0")),
            fees_paid=Decimal("0"),
            net_pnl=sum((t.net_pnl for t in trades), Decimal("0")),
            trades=trades,
        )
