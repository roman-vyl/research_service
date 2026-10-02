"""Exact sums of quantities.

`Decimal` arithmetic rounds to the context precision (28 digits). A
reduction quantity `fraction x Q0` with a non-round fraction already uses
that precision, so `Q0 - sum(reductions)` and `sum(fills)` differ in the
last digit when computed at the default precision. Quantities of a ladder
are therefore added and subtracted under a context wide enough that the
operations are exact, so a trade's fill quantities always add up to its
quantity."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, localcontext

_EXACT_PRECISION = 100


def exact_sum(values: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        return sum(values, Decimal("0"))


def exact_remainder(total: Decimal, parts: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        return total - sum(parts, Decimal("0"))
