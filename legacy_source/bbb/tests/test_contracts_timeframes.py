"""Phase 5: single source of truth for supported timeframes."""

import pytest

from data_engine.contracts.timeframes import (
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_SPECS,
    bybit_interval,
    pandas_freq_alias,
    timeframe_ms,
    validate_timeframe,
)


def test_supported_list_matches_spec_table() -> None:
    assert SUPPORTED_TIMEFRAMES == tuple(s.id for s in TIMEFRAME_SPECS)
    assert SUPPORTED_TIMEFRAMES == ("5m", "15m", "1h", "4h", "1d")


def test_validate_timeframe_strips_and_rejects() -> None:
    assert validate_timeframe("  1h ") == "1h"
    with pytest.raises(ValueError, match="unsupported"):
        validate_timeframe("1m")
    with pytest.raises(ValueError, match="supported:"):
        validate_timeframe("2h")


@pytest.mark.parametrize(
    "tf,ms,interval,pandas_f",
    [
        ("5m", 300_000, "5", "5min"),
        ("15m", 900_000, "15", "15min"),
        ("1h", 3_600_000, "60", "1h"),
        ("4h", 14_400_000, "240", "4h"),
        ("1d", 86_400_000, "D", "1D"),
    ],
)
def test_timeframe_derivatives_match_bybit_contract(
    tf: str, ms: int, interval: str, pandas_f: str
) -> None:
    assert timeframe_ms(tf) == ms
    assert bybit_interval(tf) == interval
    assert pandas_freq_alias(tf) == pandas_f
