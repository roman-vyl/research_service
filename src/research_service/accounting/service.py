"""Realised trade accounting service."""

from __future__ import annotations

from decimal import Decimal

from research_service.accounting.contracts import (
    AccountingPolicy,
    TradeAccountingResult,
    TradePathMetrics,
    TradeRecord,
)
from research_service.domain.contracts import MarketFrame
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionLoopResult, PositionExecution


def account_execution_loop(
    execution: ExecutionLoopResult,
    market: MarketFrame,
    policy: AccountingPolicy,
) -> TradeAccountingResult:
    """Convert completed position executions into realised trade records."""

    if execution.market != market.market:
        raise InvalidRequest("execution result and market frame differ")

    equity = policy.initial_equity
    records: list[TradeRecord] = []
    for position_execution in execution.positions:
        if position_execution.status == "open":
            continue
        record = _account_closed_execution(
            position_execution,
            market,
            policy,
            equity_before=equity,
            ordinal=len(records) + 1,
        )
        records.append(record)
        equity = record.equity_after

    gross = sum((item.gross_pnl for item in records), Decimal("0"))
    fees = sum((item.fees_paid for item in records), Decimal("0"))
    net = sum((item.net_pnl for item in records), Decimal("0"))
    return TradeAccountingResult(
        instance_id=execution.instance_id,
        initial_equity=policy.initial_equity,
        final_equity=equity,
        realised_trade_count=len(records),
        open_position_count=1 if execution.final_open_position is not None else 0,
        gross_pnl=gross,
        fees_paid=fees,
        net_pnl=net,
        trades=tuple(records),
    )


def _account_closed_execution(
    execution: PositionExecution,
    market: MarketFrame,
    policy: AccountingPolicy,
    *,
    equity_before: Decimal,
    ordinal: int,
) -> TradeRecord:
    exit_fill = execution.exit_fill
    if exit_fill is None:
        raise InvalidRequest("closed position execution has no exit fill")
    entry = execution.position.entry_fill
    if exit_fill.bar_index >= len(market.candles):
        raise InvalidRequest("exit bar is outside market frame")

    quantity = entry.quantity
    if execution.position.side == "long":
        gross = (exit_fill.fill_price - entry.fill_price) * quantity
    else:
        gross = (entry.fill_price - exit_fill.fill_price) * quantity

    entry_notional = abs(entry.fill_price * quantity)
    exit_notional = abs(exit_fill.fill_price * quantity)
    entry_fee = entry_notional * policy.entry_fee_rate
    exit_fee = exit_notional * policy.exit_fee_rate
    fees = entry_fee + exit_fee
    net = gross - fees
    path = _calculate_path(execution, market)
    hold_bars = exit_fill.bar_index - entry.bar_index + 1

    return TradeRecord(
        trade_id=f"trade:{execution.position.position_id}:{ordinal}",
        position_id=execution.position.position_id,
        instance_id=execution.position.instance_id,
        side=execution.position.side,
        entry_bar_index=entry.bar_index,
        exit_bar_index=exit_fill.bar_index,
        entry_time_ms=entry.time_ms,
        exit_time_ms=exit_fill.time_ms,
        entry_price=entry.fill_price,
        exit_price=exit_fill.fill_price,
        quantity=quantity,
        entry_notional=entry_notional,
        exit_notional=exit_notional,
        gross_pnl=gross,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        fees_paid=fees,
        net_pnl=net,
        gross_return_pct=gross / entry_notional,
        net_return_pct=net / entry_notional,
        equity_before=equity_before,
        equity_after=equity_before + net,
        hold_bars=hold_bars,
        hold_ms=exit_fill.time_ms - entry.time_ms,
        exit_candidate_type=exit_fill.candidate_type,
        exit_reason=exit_fill.reason,
        exit_layer=exit_fill.layer,
        exit_rule_id=exit_fill.rule_id,
        exit_component_id=exit_fill.component_id,
        exit_kind=exit_fill.exit_kind,
        path=path,
    )


def _calculate_path(execution: PositionExecution, market: MarketFrame) -> TradePathMetrics:
    exit_fill = execution.exit_fill
    assert exit_fill is not None
    entry = execution.position.entry_fill
    candles = market.candles[entry.bar_index : exit_fill.bar_index + 1]
    if not candles:
        raise InvalidRequest("trade path has no market candles")

    if execution.position.side == "long":
        favorable = [candle.high - entry.fill_price for candle in candles]
        adverse = [entry.fill_price - candle.low for candle in candles]
        realised = exit_fill.fill_price - entry.fill_price
    else:
        favorable = [entry.fill_price - candle.low for candle in candles]
        adverse = [candle.high - entry.fill_price for candle in candles]
        realised = entry.fill_price - exit_fill.fill_price

    mfe_raw = max(favorable)
    mae_raw = max(adverse)
    mfe = max(Decimal("0"), mfe_raw)
    mae = max(Decimal("0"), mae_raw)
    mfe_offset = favorable.index(mfe_raw) if mfe_raw > 0 else 0
    mae_offset = adverse.index(mae_raw) if mae_raw > 0 else 0
    capture_ratio = realised / mfe if mfe > 0 else None
    giveback = max(Decimal("0"), mfe - realised) if mfe > 0 else None

    return TradePathMetrics(
        mfe_price=mfe,
        mfe_pct=mfe / entry.fill_price,
        mfe_bar_index=entry.bar_index + mfe_offset,
        mfe_bars_from_entry=mfe_offset,
        mae_price=mae,
        mae_pct=mae / entry.fill_price,
        mae_bar_index=entry.bar_index + mae_offset,
        mae_bars_from_entry=mae_offset,
        captured_price=realised,
        captured_pct=realised / entry.fill_price,
        capture_ratio=capture_ratio,
        giveback_price=giveback,
        giveback_pct=(giveback / entry.fill_price) if giveback is not None else None,
        bars_from_mfe_to_exit=exit_fill.bar_index - (entry.bar_index + mfe_offset),
    )
