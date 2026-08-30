"""Trade accounting for completed executions.

This module owns realised financial facts only. Strategy semantics and market
fill arbitration are upstream concerns.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AccountingPolicy(BaseModel):
    """Research-owned accounting assumptions."""

    model_config = ConfigDict(frozen=True)

    initial_equity: Decimal = Field(default=Decimal("10000"), gt=0)
    entry_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    exit_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)


class TradePathMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    mfe_price: Decimal = Field(ge=0)
    mfe_pct: Decimal = Field(ge=0)
    mfe_bar_index: int = Field(ge=0)
    mfe_bars_from_entry: int = Field(ge=0)
    mae_price: Decimal = Field(ge=0)
    mae_pct: Decimal = Field(ge=0)
    mae_bar_index: int = Field(ge=0)
    mae_bars_from_entry: int = Field(ge=0)
    captured_price: Decimal
    captured_pct: Decimal
    capture_ratio: Decimal | None = None
    giveback_price: Decimal | None = Field(default=None, ge=0)
    giveback_pct: Decimal | None = Field(default=None, ge=0)
    bars_from_mfe_to_exit: int = Field(ge=0)


class TradeRecord(BaseModel):
    """Immutable realised trade record."""

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    side: Literal["long", "short"]
    status: Literal["closed"] = "closed"
    entry_bar_index: int = Field(ge=0)
    exit_bar_index: int = Field(ge=0)
    entry_time_ms: int = Field(ge=0)
    exit_time_ms: int = Field(ge=0)
    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    entry_notional: Decimal = Field(gt=0)
    exit_notional: Decimal = Field(gt=0)
    gross_pnl: Decimal
    entry_fee: Decimal = Field(ge=0)
    exit_fee: Decimal = Field(ge=0)
    fees_paid: Decimal = Field(ge=0)
    net_pnl: Decimal
    gross_return_pct: Decimal
    net_return_pct: Decimal
    equity_before: Decimal = Field(gt=0)
    equity_after: Decimal
    hold_bars: int = Field(ge=1)
    hold_ms: int = Field(ge=0)
    exit_candidate_type: str = Field(min_length=1)
    exit_reason: str = Field(min_length=1)
    exit_layer: str = Field(min_length=1)
    exit_rule_id: str | None = None
    exit_component_id: str | None = None
    exit_kind: str | None = None
    path: TradePathMetrics

    @model_validator(mode="after")
    def validate_arithmetic(self) -> "TradeRecord":
        if self.exit_bar_index < self.entry_bar_index:
            raise ValueError("exit must not precede entry")
        if self.fees_paid != self.entry_fee + self.exit_fee:
            raise ValueError("fees_paid differs from entry_fee + exit_fee")
        if self.net_pnl != self.gross_pnl - self.fees_paid:
            raise ValueError("net_pnl differs from gross_pnl - fees_paid")
        if self.equity_after != self.equity_before + self.net_pnl:
            raise ValueError("equity_after differs from equity_before + net_pnl")
        return self


#: Sanity-check tolerance for the aggregate `final_equity` vs.
#: `initial_equity + net_pnl` cross-check below -- deliberately NOT business
#: semantics (no trading/monetary quantity is ever meaningfully "equal within
#: this margin"). It exists only because the equity chain
#: (`initial_equity` -> `equity_after` -> `equity_after` -> ...) and the
#: independent `sum(trade.net_pnl)` are two different Decimal accumulation
#: paths over the same values; on long trade sequences (~1900+ trades
#: observed) they can diverge in the last few digits of the default 28-digit
#: Decimal context purely from accumulated rounding, with no real financial
#: discrepancy (every `TradeRecord`'s own arithmetic, and the equity chain's
#: own continuity, are still checked exactly below). `1e-10` is many orders
#: of magnitude above the observed ~1e-23 residue and many orders of
#: magnitude below any real monetary difference this check could otherwise
#: catch -- it is a numerical-residue allowance, not a rounding rule for
#: money.
_EQUITY_RESIDUE_TOLERANCE = Decimal("1e-10")


class TradeAccountingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_trade_accounting.v1"] = "research_trade_accounting.v1"
    instance_id: str = Field(min_length=1)
    initial_equity: Decimal = Field(gt=0)
    final_equity: Decimal
    realised_trade_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0, le=1)
    gross_pnl: Decimal
    fees_paid: Decimal = Field(ge=0)
    net_pnl: Decimal
    trades: tuple[TradeRecord, ...]

    @model_validator(mode="after")
    def validate_totals(self) -> "TradeAccountingResult":
        if self.realised_trade_count != len(self.trades):
            raise ValueError("realised_trade_count differs from trades length")
        if self.gross_pnl != sum((item.gross_pnl for item in self.trades), Decimal("0")):
            raise ValueError("gross_pnl total is inconsistent")
        if self.fees_paid != sum((item.fees_paid for item in self.trades), Decimal("0")):
            raise ValueError("fees total is inconsistent")
        if self.net_pnl != sum((item.net_pnl for item in self.trades), Decimal("0")):
            raise ValueError("net_pnl total is inconsistent")

        # Strict equity-chain continuity: each trade's equity_before must be
        # exactly the previous trade's equity_after (or initial_equity, for
        # the first trade), and final_equity must be exactly the last
        # trade's equity_after. This is the real structural guarantee --
        # unlike the aggregate cross-check below, it is never relaxed.
        previous_equity_after = self.initial_equity
        for index, trade in enumerate(self.trades):
            if trade.equity_before != previous_equity_after:
                raise ValueError(
                    f"trade {index} equity_before does not chain from the previous "
                    "trade's equity_after (or initial_equity, for the first trade)"
                )
            previous_equity_after = trade.equity_after
        if self.trades and self.final_equity != self.trades[-1].equity_after:
            raise ValueError("final_equity differs from the last trade's equity_after")
        if not self.trades and self.final_equity != self.initial_equity:
            raise ValueError("final_equity differs from initial_equity with no trades")

        # Aggregate sanity check only, not a structural guarantee -- the
        # equity chain above and each TradeRecord's own arithmetic are what
        # actually prove correctness. This just catches a real discrepancy
        # this cross-check could still expose (e.g. a chain that was built
        # from a different net_pnl total than the one reported here), while
        # tolerating pure Decimal-accumulation residue on long chains.
        residue = abs(self.final_equity - (self.initial_equity + self.net_pnl))
        if residue > _EQUITY_RESIDUE_TOLERANCE:
            raise ValueError("final equity is inconsistent with initial_equity + net_pnl")
        return self
