"""Fill quantities of a laddered trade add up to its quantity exactly, for
any entry quantity and any fraction (`research-trade-accounting-v1`
"Exit fill ledger"). `Decimal` rounds at 28 digits, so `0.33 x Q0` and
`Q0 - 0.33 x Q0` can disagree in the last digit when summed at the
default precision."""

from __future__ import annotations

import random
from decimal import Decimal, localcontext

import pytest
from partial_take_harness import FLAT, frame, run

from research_service.accounting import AccountingPolicy, account_execution_loop

_BARS = [
    FLAT,
    ("100", "101.5", "100", "101"),
    ("101", "104", "100", "103"),
    ("103", "103", "94", "95"),
]


# 28-digit quantities (equity / price); each one made the old default-precision
# sums disagree in the last digit for the fraction in the same row.
_KNOWN = [
    (Decimal("2537.021326278992574527464653"), 0.33),
    (Decimal("16132.43624789004099348926935"), 0.3),
    (Decimal("1887.571548852893919979115375"), 0.34),
]


def _trade(quantity: Decimal, fraction: float):
    result = run(
        "long",
        _BARS[1:],
        entry_bar=_BARS[0],
        legs=[("tp1", 0.01, fraction)],
        quantity=quantity,
    )
    accounting = account_execution_loop(
        result, frame(_BARS), AccountingPolicy(initial_equity=Decimal("10") ** 15)
    )
    (trade,) = accounting.trades
    return trade


def _assert_exact(trade) -> None:  # type: ignore[no-untyped-def]
    with localcontext() as context:
        context.prec = 100
        total = sum((item.quantity for item in trade.exit_fills), Decimal(0))
    assert total == trade.quantity


@pytest.mark.parametrize(("quantity", "fraction"), _KNOWN)
def test_known_quantities_that_broke_the_default_precision_sums(
    quantity: Decimal, fraction: float
) -> None:
    trade = _trade(quantity, fraction)
    assert trade.quantity == quantity
    _assert_exact(trade)


@pytest.mark.parametrize("fraction", [0.33, 0.3, 0.34, 0.1, 0.7 / 3])
def test_fills_add_up_to_the_trade_quantity(fraction: float) -> None:
    rng = random.Random(2)
    for _ in range(400):
        quantity = (
            Decimal(rng.randint(10**6, 10**7))
            * Decimal(rng.randint(10**3, 10**4))
            / Decimal(rng.randint(10**4, 10**5))
            / Decimal(rng.randint(3, 97))
        )
        _assert_exact(_trade(quantity, fraction))
