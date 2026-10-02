"""Trade accounting for completed executions.

This module owns realised financial facts only. Strategy semantics and market
fill arbitration are upstream concerns.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from research_service.domain.exact_decimal import exact_sum


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


class TradeExitFill(BaseModel):
    """One exit fill of a laddered trade (`research-trade-accounting-v1`
    "One trade record per strategic position"): a partial take reduction
    or the final fill that closed the remainder."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["partial_take", "final"]
    take_id: str | None = None
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    notional: Decimal = Field(gt=0)
    fee: Decimal = Field(ge=0)
    rule_id: str | None = None
    component_id: str | None = None
    exit_kind: str | None = None

    @model_validator(mode="after")
    def validate_kind(self) -> "TradeExitFill":
        if (self.kind == "partial_take") != (self.take_id is not None):
            raise ValueError("take_id is set exactly on partial_take fills")
        return self


class TradeRecord(BaseModel):
    """Immutable realised trade record.

    One strategic position is one record. A position with partial take
    reductions keeps `quantity` = Q0 and `exit_price` = the closing fill,
    and adds `exit_fills` (every exit fill in execution order) and
    `average_exit_price`. Both are empty for a single-fill trade and
    omitted on dump, so such a record is unchanged."""

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
    # Trade-native R accounting (`research-trade-native-r-v1`). Denominator
    # is frozen at entry -- |entry_fill.fill_price - initial stop price| --
    # and never re-derived from a later managed-exit level, so it stays a
    # stable per-trade risk unit regardless of what actually closed the
    # trade or how the position was sized. All four fields are set together
    # from the position's `initial_protection.stop_loss_price`; when that is
    # `None` (no initial stop configured), all four stay `None` and the
    # trade remains otherwise fully valid -- R eligibility is optional, not
    # a validity requirement.
    initial_risk_price: Decimal | None = Field(default=None, gt=0)
    initial_risk_amount: Decimal | None = Field(default=None, gt=0)
    gross_r_multiple: Decimal | None = None
    net_r_multiple: Decimal | None = None
    exit_fills: tuple[TradeExitFill, ...] = ()
    average_exit_price: Decimal | None = Field(default=None, gt=0)

    @model_serializer(mode="wrap")
    def _omit_empty_ladder_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if not self.exit_fills:
            data.pop("exit_fills", None)
        if self.average_exit_price is None:
            data.pop("average_exit_price", None)
        return data

    @model_validator(mode="after")
    def validate_exit_fills(self) -> "TradeRecord":
        if not self.exit_fills:
            if self.average_exit_price is not None:
                raise ValueError("average_exit_price requires exit_fills")
            return self
        if self.average_exit_price is None:
            raise ValueError("exit_fills require average_exit_price")
        *partials, final = self.exit_fills
        if final.kind != "final" or any(item.kind != "partial_take" for item in partials):
            raise ValueError("exit_fills must be partial takes followed by one final fill")
        if final.price != self.exit_price or final.bar_index != self.exit_bar_index:
            raise ValueError("the final exit fill must be the closing fill")
        if exact_sum(item.quantity for item in self.exit_fills) != self.quantity:
            raise ValueError("exit fill quantities differ from quantity")
        if sum((item.notional for item in self.exit_fills), Decimal("0")) != self.exit_notional:
            raise ValueError("exit fill notionals differ from exit_notional")
        if sum((item.fee for item in self.exit_fills), Decimal("0")) != self.exit_fee:
            raise ValueError("exit fill fees differ from exit_fee")
        if self.average_exit_price != self.exit_notional / self.quantity:
            raise ValueError("average_exit_price differs from exit_notional / quantity")
        return self

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

        r_fields = (
            self.initial_risk_price,
            self.initial_risk_amount,
            self.gross_r_multiple,
            self.net_r_multiple,
        )
        if any(value is None for value in r_fields) and any(
            value is not None for value in r_fields
        ):
            raise ValueError(
                "initial_risk_price, initial_risk_amount, gross_r_multiple, "
                "net_r_multiple must be all set or all None together"
            )
        if self.initial_risk_amount is not None:
            assert self.initial_risk_price is not None
            assert self.gross_r_multiple is not None
            assert self.net_r_multiple is not None
            if self.initial_risk_amount != self.initial_risk_price * self.quantity:
                raise ValueError("initial_risk_amount differs from initial_risk_price * quantity")
            if self.gross_r_multiple != self.gross_pnl / self.initial_risk_amount:
                raise ValueError("gross_r_multiple differs from gross_pnl / initial_risk_amount")
            if self.net_r_multiple != self.net_pnl / self.initial_risk_amount:
                raise ValueError("net_r_multiple differs from net_pnl / initial_risk_amount")
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
