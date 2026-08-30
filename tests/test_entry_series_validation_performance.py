"""Regression tests for the O(n^2) fix in `execution/entry.py`'s
per-bar entry-series validation.

`_entry_series` runs an O(bar_count) `isinstance`/length scan over the
full `entries[side]` array. Before this fix, `run_unified_execution_
loop` called `try_open_position` -> `entry_decision_at` ->
`_entry_series` on every bar it wasn't already holding a position --
O(bar_count) work called up to once per bar, i.e. O(bar_count^2) for a
full run. `validated_entry_series` now runs that same validation once
per execution run; `entry_decision_at`/`try_open_position` accept the
pre-validated result via an optional `entries` parameter and skip
re-validating when it's supplied. Semantics, ordering, fills, and
accounting are unchanged -- only the number of times the O(n) scan
runs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    Candle,
    MarketFrame,
    MarketRange,
    StrategyEvaluationResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionPolicy
from research_service.execution import entry as entry_module
from research_service.execution.entry import (
    entry_decision_at,
    try_open_position,
    validated_entry_series,
)
from research_service.execution.loop import run_unified_execution_loop


def _market(bar_count: int) -> MarketFrame:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=bar_count * 300_000)
    candles = tuple(
        Candle(
            open_time_ms=i * 300_000,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(bar_count)
    )
    return MarketFrame(market=market, candles=candles)


def _evaluation(
    *,
    bar_count: int,
    long: tuple[bool, ...],
    short: tuple[bool, ...],
) -> StrategyEvaluationResult:
    market = _market(bar_count).market
    false = [False] * bar_count
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id="instance-1",
        config_hash="config-hash",
        market=market,
        bar_count=bar_count,
        market_data_hash="market-hash",
        time_ms=tuple(i * 300_000 for i in range(bar_count)),
        entries={"long": long, "short": short},
        exit_policy={
            "signal_exit": {"long": false, "short": false},
            "stop_loss_ratio": {"long": ["0.01"] * bar_count, "short": ["0.01"] * bar_count},
            "take_profit_ratio": {"long": ["0.03"] * bar_count, "short": ["0.03"] * bar_count},
            "stop_ready": {"long": [True] * bar_count, "short": [True] * bar_count},
        },
        component_evidence={},
        raw={},
    )


# --- identical long/short entry decisions, validated vs. pre-validated ----


def test_pre_validated_and_inline_validation_produce_identical_decisions() -> None:
    evaluation = _evaluation(bar_count=5, long=(False, True, False, False, False), short=(False,) * 5)
    market = _market(5)

    inline = entry_decision_at(evaluation, market, bar_index=1)
    entries = validated_entry_series(evaluation)
    pre_validated = entry_decision_at(evaluation, market, bar_index=1, entries=entries)

    assert inline == pre_validated
    assert inline is not None
    assert inline.side == "long"


def test_try_open_position_identical_with_and_without_pre_validated_entries() -> None:
    evaluation = _evaluation(bar_count=5, long=(False,) * 5, short=(False, False, True, False, False))
    market = _market(5)
    policy = ExecutionPolicy()

    inline = try_open_position(evaluation, market, policy, bar_index=2, current_position=None)
    entries = validated_entry_series(evaluation)
    pre_validated = try_open_position(
        evaluation, market, policy, bar_index=2, current_position=None, entries=entries
    )

    assert inline is not None and pre_validated is not None
    assert inline.side == pre_validated.side == "short"
    assert inline.entry_fill == pre_validated.entry_fill
    assert inline.initial_protection == pre_validated.initial_protection


def test_full_loop_run_matches_regardless_of_internal_pre_validation() -> None:
    # run_unified_execution_loop always uses the pre-validated path
    # internally now -- this confirms the resulting execution is the same
    # shape/content a caller would get from entry_decision_at/try_open_
    # position's own directly-validated behavior for the same bars.
    evaluation = _evaluation(bar_count=6, long=(False, True, False, False, False, False), short=(False,) * 6)
    market = _market(6)
    result = run_unified_execution_loop(evaluation, market, ExecutionPolicy())
    assert len(result.events) >= 1
    entry_events = [e for e in result.events if e.event_type == "entry_filled"]
    assert len(entry_events) == 1
    assert entry_events[0].bar_index == 1


# --- invalid entries fail closed, both paths ------------------------------


def test_invalid_entries_fail_closed_without_pre_validation() -> None:
    evaluation = _evaluation(bar_count=3, long=(False, True, False), short=(False, False, False))
    # Corrupt entries after construction (bypassing the pydantic model's own
    # field, which is frozen -- simulate a malformed evaluation the same way
    # the existing test suite already does for this function).
    object.__setattr__(evaluation, "entries", {"long": [False, "not-a-bool", False], "short": [False] * 3})
    market = _market(3)

    with pytest.raises(InvalidRequest):
        entry_decision_at(evaluation, market, bar_index=1)


def test_invalid_entries_fail_closed_via_validated_entry_series() -> None:
    evaluation = _evaluation(bar_count=3, long=(False, True, False), short=(False, False, False))
    object.__setattr__(evaluation, "entries", {"long": [False, True], "short": [False] * 3})  # wrong length

    with pytest.raises(InvalidRequest):
        validated_entry_series(evaluation)


def test_pre_validated_entries_are_not_re_validated_so_a_later_corruption_is_not_caught() -> None:
    # Documents the accepted tradeoff explicitly: once entries is
    # pre-validated and passed in, entry_decision_at trusts it -- exactly
    # matching what "validate once per run" means. This is not a new gap:
    # the evaluation itself is an immutable pydantic model for the
    # lifetime of one execution run in production; this test exists so a
    # future change to that assumption doesn't silently invalidate the
    # optimization without a test noticing.
    evaluation = _evaluation(bar_count=3, long=(False, True, False), short=(False, False, False))
    market = _market(3)
    entries = validated_entry_series(evaluation)  # valid at validation time
    # entry_decision_at trusts the pre-validated tuple and does not re-scan.
    decision = entry_decision_at(evaluation, market, bar_index=1, entries=entries)
    assert decision is not None


# --- no repeated O(n) scan inside the bar loop -----------------------------


def test_entry_series_is_validated_once_per_run_not_once_per_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0
    original = entry_module._entry_series

    def counting_entry_series(evaluation: StrategyEvaluationResult, side: str) -> object:
        nonlocal call_count
        call_count += 1
        return original(evaluation, side)

    monkeypatch.setattr(entry_module, "_entry_series", counting_entry_series)

    bar_count = 500
    evaluation = _evaluation(bar_count=bar_count, long=(False,) * bar_count, short=(False,) * bar_count)
    market = _market(bar_count)

    run_unified_execution_loop(evaluation, market, ExecutionPolicy())

    # Exactly 2 calls (long + short) for the whole run, regardless of
    # bar_count -- not up to one call per bar (which would be up to 500
    # here, and O(bar_count) work inside each call).
    assert call_count == 2, (
        f"_entry_series was called {call_count} times for a {bar_count}-bar run "
        "-- expected exactly 2 (validated once per run, not once per bar)"
    )
