from __future__ import annotations

from decimal import Decimal
from typing import Literal

from research_service.accounting.contracts import (
    TradeAccountingResult,
    TradePathMetrics,
    TradeRecord,
)
from research_service.application.experiments.candidate_summary import (
    _max_drawdown,
    derive_batch_candidate_summary,
)

_PATH = TradePathMetrics(
    mfe_price=Decimal("1"),
    mfe_pct=Decimal("0"),
    mfe_bar_index=0,
    mfe_bars_from_entry=0,
    mae_price=Decimal("1"),
    mae_pct=Decimal("0"),
    mae_bar_index=0,
    mae_bars_from_entry=0,
    captured_price=Decimal("1"),
    captured_pct=Decimal("0"),
    bars_from_mfe_to_exit=0,
)


def trade(
    net_pnl: Decimal,
    equity_before: Decimal,
    side: Literal["long", "short"] = "long",
    trade_id: str = "t",
) -> TradeRecord:
    gross_pnl = net_pnl
    return TradeRecord(
        trade_id=trade_id,
        position_id=trade_id,
        instance_id="i",
        side=side,
        entry_bar_index=0,
        exit_bar_index=1,
        entry_time_ms=0,
        exit_time_ms=1,
        entry_price=Decimal("1"),
        exit_price=Decimal("1"),
        quantity=Decimal("1"),
        entry_notional=Decimal("100"),
        exit_notional=Decimal("100"),
        gross_pnl=gross_pnl,
        entry_fee=Decimal("0"),
        exit_fee=Decimal("0"),
        fees_paid=Decimal("0"),
        net_pnl=net_pnl,
        gross_return_pct=gross_pnl / Decimal("100"),
        net_return_pct=net_pnl / Decimal("100"),
        equity_before=equity_before,
        equity_after=equity_before + net_pnl,
        hold_bars=1,
        hold_ms=1,
        exit_candidate_type="x",
        exit_reason="x",
        exit_layer="x",
        path=_PATH,
    )


def accounting(trades: tuple[TradeRecord, ...], initial_equity: Decimal = Decimal("1000")) -> TradeAccountingResult:
    gross = sum((t.gross_pnl for t in trades), Decimal("0"))
    fees = sum((t.fees_paid for t in trades), Decimal("0"))
    net = sum((t.net_pnl for t in trades), Decimal("0"))
    return TradeAccountingResult(
        instance_id="i",
        initial_equity=initial_equity,
        final_equity=initial_equity + net,
        realised_trade_count=len(trades),
        open_position_count=0,
        gross_pnl=gross,
        fees_paid=fees,
        net_pnl=net,
        trades=trades,
    )


def test_zero_trades_produces_null_metrics_and_zero_scalars() -> None:
    summary = derive_batch_candidate_summary(accounting(()))

    assert summary.return_pct == Decimal("0")
    assert summary.win_rate is None
    assert summary.profit_factor is None
    assert summary.max_drawdown == Decimal("0")
    for side in (summary.long, summary.short):
        assert side.trades == 0
        assert side.net_pnl == Decimal("0")
        assert side.return_pct == Decimal("0")
        assert side.win_rate is None
        assert side.profit_factor is None


def test_all_winners_profit_factor_is_null() -> None:
    trades = (
        trade(Decimal("10"), Decimal("1000")),
        trade(Decimal("20"), Decimal("1010")),
    )
    summary = derive_batch_candidate_summary(accounting(trades))

    assert summary.win_rate == Decimal("1")
    assert summary.profit_factor is None
    assert summary.return_pct == Decimal("30") / Decimal("1000")


def test_all_losers_profit_factor_is_zero() -> None:
    trades = (
        trade(Decimal("-10"), Decimal("1000")),
        trade(Decimal("-5"), Decimal("990")),
    )
    summary = derive_batch_candidate_summary(accounting(trades))

    assert summary.win_rate == Decimal("0")
    assert summary.profit_factor == Decimal("0")


def test_mixed_trades_profit_factor_and_win_rate() -> None:
    trades = (
        trade(Decimal("20"), Decimal("1000")),
        trade(Decimal("-10"), Decimal("1020")),
        trade(Decimal("0"), Decimal("1010")),  # break-even, not a winner
    )
    summary = derive_batch_candidate_summary(accounting(trades))

    assert summary.win_rate == Decimal("1") / Decimal("3")
    assert summary.profit_factor == Decimal("2")


def test_max_drawdown_is_trade_close_running_peak_trough() -> None:
    trades = (
        trade(Decimal("100"), Decimal("1000")),  # equity 1100, new peak
        trade(Decimal("-330"), Decimal("1100")),  # equity 770, trough vs peak 1100
        trade(Decimal("50"), Decimal("770")),  # equity 820, still below peak
    )
    summary = derive_batch_candidate_summary(accounting(trades))

    # 770 / 1100 - 1 = -0.3
    assert summary.max_drawdown == Decimal("770") / Decimal("1100") - 1


def test_side_split_isolates_long_and_short_trades() -> None:
    trades = (
        trade(Decimal("10"), Decimal("1000"), side="long"),
        trade(Decimal("-5"), Decimal("1010"), side="short"),
        trade(Decimal("15"), Decimal("1005"), side="short"),
    )
    summary = derive_batch_candidate_summary(accounting(trades))

    assert summary.long.trades == 1
    assert summary.long.net_pnl == Decimal("10")
    assert summary.long.win_rate == Decimal("1")
    assert summary.long.profit_factor is None

    assert summary.short.trades == 2
    assert summary.short.net_pnl == Decimal("10")
    assert summary.short.win_rate == Decimal("1") / Decimal("2")
    assert summary.short.profit_factor == Decimal("3")


def test_max_drawdown_uses_equity_before_not_only_equity_after() -> None:
    # trade1: 1000 -> 1200 (new peak 1200)
    # trade2: equity_before=400 (a dip not reflected in any equity_after,
    #         i.e. equity_before != previous trade's equity_after) then
    #         recovers to equity_after=1200 within the same trade.
    # A drawdown implementation that only inspects equity_after per trade
    # would report 0 here; the normative equity-chain walk must catch the
    # 400/1200-1 dip at equity_before.
    #
    # This deliberately breaks TradeAccountingResult's own equity-chain
    # continuity invariant (each trade's equity_before must equal the
    # previous trade's equity_after) -- a state that can never occur in
    # real accounting output. It exists only to unit-test `_max_drawdown`'s
    # walk in isolation, so it calls that pure function directly instead
    # of round-tripping through TradeAccountingResult's validation.
    trades = (
        trade(Decimal("200"), Decimal("1000")),  # equity_after = 1200
        TradeRecord(
            trade_id="t2",
            position_id="t2",
            instance_id="i",
            side="long",
            entry_bar_index=0,
            exit_bar_index=1,
            entry_time_ms=0,
            exit_time_ms=1,
            entry_price=Decimal("1"),
            exit_price=Decimal("1"),
            quantity=Decimal("1"),
            entry_notional=Decimal("100"),
            exit_notional=Decimal("100"),
            gross_pnl=Decimal("800"),
            entry_fee=Decimal("0"),
            exit_fee=Decimal("0"),
            fees_paid=Decimal("0"),
            net_pnl=Decimal("800"),
            gross_return_pct=Decimal("8"),
            net_return_pct=Decimal("8"),
            equity_before=Decimal("400"),
            equity_after=Decimal("1200"),
            hold_bars=1,
            hold_ms=1,
            exit_candidate_type="x",
            exit_reason="x",
            exit_layer="x",
            path=_PATH,
        ),
    )
    max_drawdown = _max_drawdown(trades, Decimal("1000"))

    assert max_drawdown == Decimal("400") / Decimal("1200") - 1
