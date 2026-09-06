"""Derive compact research-comparison metrics for one batch candidate.

Pure function over an already-materialized canonical result's trade list
-- no I/O, no Engine access, no disk read. Formulas fixed by
`research-batch-experiments-v1` ("Batch output shape",
"BatchSideSummary shape"): all metrics use net PnL after fees.
"""

from __future__ import annotations

from decimal import Decimal

from research_service.accounting.contracts import TradeAccountingResult, TradeRecord
from research_service.application.experiments.contracts import BatchSideSummary


def _win_rate(trades: tuple[TradeRecord, ...]) -> Decimal | None:
    if not trades:
        return None
    winners = sum(1 for trade in trades if trade.net_pnl > 0)
    return Decimal(winners) / Decimal(len(trades))


def _cumulative_risk_outcome(n: int, wr: Decimal | None) -> Decimal:
    if n == 0:
        return Decimal("0")
    if wr is None or not (Decimal(0) <= wr <= Decimal(1)):
        raise ValueError(f"win_rate must be in [0, 1] for n > 0, got {wr!r}")
    return Decimal(n) * (2 * wr - 1)


def _profit_factor(trades: tuple[TradeRecord, ...]) -> Decimal | None:
    gains = sum((trade.net_pnl for trade in trades if trade.net_pnl > 0), Decimal("0"))
    losses = sum((trade.net_pnl for trade in trades if trade.net_pnl < 0), Decimal("0"))
    if losses == 0:
        return None
    return gains / abs(losses)


def _max_drawdown(trades: tuple[TradeRecord, ...], initial_equity: Decimal) -> Decimal:
    """Walk the ordered closed-trade equity chain explicitly, visiting each
    trade's `equity_before` then `equity_after` -- never assuming
    `trade[i].equity_after == trade[i + 1].equity_before` (that continuity
    is not a contract invariant)."""
    peak = initial_equity
    trough = Decimal("0")
    for trade in trades:
        for equity in (trade.equity_before, trade.equity_after):
            if equity > peak:
                peak = equity
            drawdown = equity / peak - 1
            if drawdown < trough:
                trough = drawdown
    return trough


def _side_summary(trades: tuple[TradeRecord, ...], initial_equity: Decimal) -> BatchSideSummary:
    net_pnl = sum((trade.net_pnl for trade in trades), Decimal("0"))
    win_rate = _win_rate(trades)
    return BatchSideSummary(
        trades=len(trades),
        net_pnl=net_pnl,
        return_pct=net_pnl / initial_equity,
        win_rate=win_rate,
        profit_factor=_profit_factor(trades),
        cumulative_risk_outcome=_cumulative_risk_outcome(len(trades), win_rate),
    )


class BatchCandidateSummary:
    """`return_pct`, `win_rate`, `profit_factor`, `max_drawdown`,
    `cumulative_risk_outcome`, and `long`/`short` `BatchSideSummary` for one
    successful batch candidate."""

    def __init__(
        self,
        return_pct: Decimal,
        win_rate: Decimal | None,
        profit_factor: Decimal | None,
        max_drawdown: Decimal,
        cumulative_risk_outcome: Decimal,
        long: BatchSideSummary,
        short: BatchSideSummary,
    ) -> None:
        self.return_pct = return_pct
        self.win_rate = win_rate
        self.profit_factor = profit_factor
        self.max_drawdown = max_drawdown
        self.cumulative_risk_outcome = cumulative_risk_outcome
        self.long = long
        self.short = short


def derive_batch_candidate_summary(accounting: TradeAccountingResult) -> BatchCandidateSummary:
    trades = accounting.trades
    initial_equity = accounting.initial_equity
    long_trades = tuple(trade for trade in trades if trade.side == "long")
    short_trades = tuple(trade for trade in trades if trade.side == "short")
    win_rate = _win_rate(trades)
    return BatchCandidateSummary(
        return_pct=accounting.net_pnl / initial_equity,
        win_rate=win_rate,
        profit_factor=_profit_factor(trades),
        max_drawdown=_max_drawdown(trades, initial_equity),
        cumulative_risk_outcome=_cumulative_risk_outcome(len(trades), win_rate),
        long=_side_summary(long_trades, initial_equity),
        short=_side_summary(short_trades, initial_equity),
    )
