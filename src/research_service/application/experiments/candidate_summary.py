"""Derive compact research-comparison metrics for one batch candidate.

Pure function over an already-materialized canonical result's trade list
-- no I/O, no Engine access, no disk read. Formulas fixed by
`research-batch-experiments-v1` ("Batch output shape",
"BatchSideSummary shape"): all metrics use net PnL after fees.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from research_service.accounting.contracts import TradeAccountingResult, TradeRecord
from research_service.application.experiments.contracts import BatchSideSummary, BatchYearSummary


def _win_rate(trades: tuple[TradeRecord, ...]) -> Decimal | None:
    if not trades:
        return None
    winners = sum(1 for trade in trades if trade.net_pnl > 0)
    return Decimal(winners) / Decimal(len(trades))


def _profit_factor(trades: tuple[TradeRecord, ...]) -> Decimal | None:
    gains = sum((trade.net_pnl for trade in trades if trade.net_pnl > 0), Decimal("0"))
    losses = sum((trade.net_pnl for trade in trades if trade.net_pnl < 0), Decimal("0"))
    if losses == 0:
        return None
    return gains / abs(losses)


def _cumulative_r(
    trades: tuple[TradeRecord, ...],
) -> tuple[Decimal, Decimal, int]:
    """Sum trade-native R over eligible trades only (those with a resolved
    `gross_r_multiple`/`net_r_multiple` -- see `accounting/service.py::
    _initial_risk`). A trade with no initial stop is silently excluded, not
    treated as R=0 -- `r_eligible_trade_count` tells the caller how many of
    `len(trades)` actually contributed, since a candidate summary line does
    not otherwise show whether ΣR covers all trades or a subset."""

    gross_multiples = [trade.gross_r_multiple for trade in trades if trade.gross_r_multiple is not None]
    net_multiples = [trade.net_r_multiple for trade in trades if trade.net_r_multiple is not None]
    gross_r = sum(gross_multiples, Decimal("0"))
    net_r = sum(net_multiples, Decimal("0"))
    return gross_r, net_r, len(gross_multiples)


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


#: Default in-sample / out-of-sample split (`research-run-period-metrics-v1`): 2023-07-01T00:00:00Z.
DEFAULT_PERIOD_SPLIT_MS = 1688169600000


def _trade_return(trade: TradeRecord) -> Decimal:
    """Per-trade return on the equity before the trade (D1): with full-equity
    sizing, compounding these from the initial equity re-accounts any subset."""
    return trade.net_pnl / trade.equity_before


def _part_net(trades: list[TradeRecord], initial_equity: Decimal) -> Decimal:
    growth = Decimal("1")
    for trade in trades:
        growth *= 1 + _trade_return(trade)
    return initial_equity * (growth - 1)


def _year(time_ms: int) -> str:
    return str(datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).year)


def _periods(
    trades: tuple[TradeRecord, ...], initial_equity: Decimal, split_ms: int
) -> tuple[Decimal, int, Decimal, int]:
    inside = [trade for trade in trades if trade.exit_time_ms < split_ms]
    outside = [trade for trade in trades if trade.exit_time_ms >= split_ms]
    return _part_net(inside, initial_equity), len(inside), _part_net(outside, initial_equity), len(outside)


def _years(trades: tuple[TradeRecord, ...]) -> dict[str, BatchYearSummary]:
    """Return of each UTC exit year over the account's own equity chain (D4)."""
    first: dict[str, Decimal] = {}
    last: dict[str, Decimal] = {}
    count: dict[str, int] = {}
    for trade in trades:
        year = _year(trade.exit_time_ms)
        first.setdefault(year, trade.equity_before)
        last[year] = trade.equity_after
        count[year] = count.get(year, 0) + 1
    return {
        year: BatchYearSummary(return_pct=last[year] / first[year] - 1, trades=count[year])
        for year in sorted(first)
    }


def _trade_averages(trades: tuple[TradeRecord, ...]) -> tuple[Decimal | None, Decimal | None]:
    """Average trade in basis points and payoff ratio of the per-trade returns (D5)."""
    if not trades:
        return None, None
    returns = [_trade_return(trade) for trade in trades]
    average_bp = sum(returns, Decimal("0")) / len(returns) * 10000
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    if not wins or not losses:
        return average_bp, None
    mean_win = sum(wins, Decimal("0")) / len(wins)
    mean_loss = sum(losses, Decimal("0")) / len(losses)
    return average_bp, mean_win / -mean_loss


def _side_summary(trades: tuple[TradeRecord, ...], initial_equity: Decimal) -> BatchSideSummary:
    net_pnl = sum((trade.net_pnl for trade in trades), Decimal("0"))
    cumulative_gross_r, cumulative_net_r, r_eligible_trade_count = _cumulative_r(trades)
    return BatchSideSummary(
        trades=len(trades),
        net_pnl=net_pnl,
        return_pct=net_pnl / initial_equity,
        win_rate=_win_rate(trades),
        profit_factor=_profit_factor(trades),
        cumulative_gross_r=cumulative_gross_r,
        cumulative_net_r=cumulative_net_r,
        r_eligible_trade_count=r_eligible_trade_count,
    )


class BatchCandidateSummary:
    """`return_pct`, `win_rate`, `profit_factor`, `max_drawdown`, trade-native
    R aggregates, and `long`/`short` `BatchSideSummary` for one successful
    batch candidate."""

    def __init__(
        self,
        return_pct: Decimal,
        win_rate: Decimal | None,
        profit_factor: Decimal | None,
        max_drawdown: Decimal,
        cumulative_gross_r: Decimal,
        cumulative_net_r: Decimal,
        r_eligible_trade_count: int,
        long: BatchSideSummary,
        short: BatchSideSummary,
        period_fields: dict[str, Any] | None = None,
    ) -> None:
        self.return_pct = return_pct
        self.win_rate = win_rate
        self.profit_factor = profit_factor
        self.max_drawdown = max_drawdown
        self.cumulative_gross_r = cumulative_gross_r
        self.cumulative_net_r = cumulative_net_r
        self.r_eligible_trade_count = r_eligible_trade_count
        self.long = long
        self.short = short
        #: `research-run-period-metrics-v1` fields, keyed by their `BatchCandidateResult` names.
        self.period_fields = period_fields or {}


def derive_period_fields(
    trades: tuple[TradeRecord, ...], initial_equity: Decimal, split_ms: int = DEFAULT_PERIOD_SPLIT_MS
) -> dict[str, Any]:
    """IS / OOS, yearly, years up, worst year, average trade and payoff of one
    candidate's ordered closed trades (`research-run-period-metrics-v1`)."""
    is_net, is_trades, oos_net, oos_trades = _periods(trades, initial_equity, split_ms)
    years = _years(trades)
    average_bp, payoff = _trade_averages(trades)
    returns = [year.return_pct for year in years.values()]
    return {
        "period_split_ms": split_ms,
        "is_net_pnl": is_net,
        "is_trades": is_trades,
        "oos_net_pnl": oos_net,
        "oos_trades": oos_trades,
        "years": years,
        "years_up": sum(1 for r in returns if r > 0),
        "worst_year": min(returns) if returns else None,
        "avg_trade_bp": average_bp,
        "payoff_ratio": payoff,
    }


def derive_batch_candidate_summary(
    accounting: TradeAccountingResult, period_split_ms: int = DEFAULT_PERIOD_SPLIT_MS
) -> BatchCandidateSummary:
    trades = accounting.trades
    initial_equity = accounting.initial_equity
    long_trades = tuple(trade for trade in trades if trade.side == "long")
    short_trades = tuple(trade for trade in trades if trade.side == "short")
    cumulative_gross_r, cumulative_net_r, r_eligible_trade_count = _cumulative_r(trades)
    return BatchCandidateSummary(
        period_fields=derive_period_fields(trades, initial_equity, period_split_ms),
        return_pct=accounting.net_pnl / initial_equity,
        win_rate=_win_rate(trades),
        profit_factor=_profit_factor(trades),
        max_drawdown=_max_drawdown(trades, initial_equity),
        cumulative_gross_r=cumulative_gross_r,
        cumulative_net_r=cumulative_net_r,
        r_eligible_trade_count=r_eligible_trade_count,
        long=_side_summary(long_trades, initial_equity),
        short=_side_summary(short_trades, initial_equity),
    )
