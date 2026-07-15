"""Query parameter validation for market endpoints."""

from __future__ import annotations

import re

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,32}$")


class MarketParamError(ValueError):
    """Invalid market query parameter."""


def normalize_symbol(symbol: str) -> str:
    candidate = symbol.strip().upper()
    if not _SYMBOL_RE.fullmatch(candidate):
        raise MarketParamError(f"Invalid symbol: {symbol!r}")
    return candidate


def parse_time_range_ms(*, from_ms: int, to_ms: int) -> tuple[int, int]:
    if from_ms < 0 or to_ms < 0:
        raise MarketParamError("from and to must be non-negative milliseconds")
    if from_ms >= to_ms:
        raise MarketParamError("from must be less than to (half-open window [from, to))")
    return from_ms, to_ms
