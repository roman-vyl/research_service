"""Research-owned canonical historical position sizing."""

from __future__ import annotations

from decimal import Decimal

from research_service.domain.errors import InvalidRequest


def calculate_full_equity_quantity(
    current_equity: Decimal,
    actual_entry_fill_price: Decimal,
    entry_fee_rate: Decimal,
) -> Decimal:
    """Return vectorbt-compatible all-in quantity for proportional fees."""

    if not current_equity.is_finite() or current_equity <= 0:
        raise InvalidRequest("current equity must be finite and positive")
    if not actual_entry_fill_price.is_finite() or actual_entry_fill_price <= 0:
        raise InvalidRequest("actual entry fill price must be finite and positive")
    if not entry_fee_rate.is_finite() or entry_fee_rate < 0 or entry_fee_rate >= 1:
        raise InvalidRequest("entry fee rate must be finite and in [0, 1)")

    quantity = current_equity / (
        actual_entry_fill_price * (Decimal("1") + entry_fee_rate)
    )
    notional = actual_entry_fill_price * quantity
    if not quantity.is_finite() or quantity <= 0:
        raise InvalidRequest("calculated quantity must be finite and positive")
    if not notional.is_finite() or notional <= 0:
        raise InvalidRequest("calculated entry notional must be finite and positive")
    return quantity
