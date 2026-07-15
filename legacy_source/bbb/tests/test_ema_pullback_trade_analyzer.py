"""Post-trade quality diagnostics for ema_pullback."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")

from research.strategies.ema_pullback.execution.trade_analyzer import (
    build_exit_component_quality_breakdown,
    build_quality_flag_breakdown,
    build_trade_quality_diagnostics,
    compute_trade_quality_metrics,
)


def _series(values: list[float]):
    return pd.Series(values, index=pd.RangeIndex(len(values)))


def test_long_trade_excursion_capture_and_atr_metrics() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=106.0,
        entry_idx=0,
        exit_idx=2,
        high=_series([101.0, 110.0, 106.0]),
        low=_series([99.0, 98.0, 103.0]),
        diagnostic_atr_series=_series([2.0, 2.0, 2.0]),
    )

    assert metrics["mfe_price"] == 10.0
    assert metrics["mfe_pct"] == 0.10
    assert metrics["mfe_atr"] == 5.0
    assert metrics["mae_price"] == 2.0
    assert metrics["mae_pct"] == 0.02
    assert metrics["mae_atr"] == 1.0
    assert metrics["bars_to_mfe"] == 1
    assert metrics["bars_to_mae"] == 1
    assert metrics["captured_price"] == 6.0
    assert metrics["captured_pct"] == 0.06
    assert metrics["captured_atr"] == 3.0
    assert metrics["capture_ratio"] == 0.6
    assert metrics["giveback_price"] == 4.0
    assert metrics["giveback_pct"] == 0.04
    assert metrics["giveback_atr"] == 2.0
    assert metrics["bars_from_mfe_to_exit"] == 1


def test_short_trade_excursion_mirrors_long_calculations() -> None:
    metrics = compute_trade_quality_metrics(
        direction="short",
        entry_price=100.0,
        exit_price=96.0,
        entry_idx=0,
        exit_idx=2,
        high=_series([101.0, 103.0, 98.0]),
        low=_series([99.0, 95.0, 96.0]),
    )

    assert metrics["mfe_price"] == 5.0
    assert metrics["mae_price"] == 3.0
    assert metrics["bars_to_mfe"] == 1
    assert metrics["bars_to_mae"] == 1
    assert metrics["captured_price"] == 4.0
    assert metrics["capture_ratio"] == 0.8
    assert metrics["giveback_price"] == 1.0


def test_one_bar_trade_uses_entry_bar_as_zero_offset() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=101.0,
        entry_idx=0,
        exit_idx=0,
        high=_series([102.0]),
        low=_series([99.0]),
    )

    assert metrics["mfe_price"] == 2.0
    assert metrics["mae_price"] == 1.0
    assert metrics["bars_to_mfe"] == 0
    assert metrics["bars_to_mae"] == 0
    assert metrics["bars_from_mfe_to_exit"] == 0


def test_entry_price_outside_ohlc_due_slippage_clamps_mfe_and_mae() -> None:
    long_metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=101.0,
        exit_price=100.0,
        entry_idx=0,
        exit_idx=0,
        high=_series([100.0]),
        low=_series([99.0]),
    )
    short_metrics = compute_trade_quality_metrics(
        direction="short",
        entry_price=99.0,
        exit_price=100.0,
        entry_idx=0,
        exit_idx=0,
        high=_series([101.0]),
        low=_series([100.0]),
    )

    assert long_metrics["mfe_price"] == 0.0
    assert long_metrics["capture_ratio"] is None
    assert long_metrics["mae_price"] == 2.0
    assert short_metrics["mfe_price"] == 0.0
    assert short_metrics["capture_ratio"] is None
    assert short_metrics["mae_price"] == 2.0


def test_zero_mfe_and_mae_reset_bar_offset_to_entry() -> None:
    long_metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=101.0,
        exit_price=100.0,
        entry_idx=0,
        exit_idx=1,
        high=_series([100.0, 100.5]),
        low=_series([99.0, 98.0]),
    )
    short_metrics = compute_trade_quality_metrics(
        direction="short",
        entry_price=99.0,
        exit_price=100.0,
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 102.0]),
        low=_series([100.0, 99.5]),
    )

    assert long_metrics["mfe_price"] == 0.0
    assert long_metrics["bars_to_mfe"] == 0
    assert long_metrics["capture_ratio"] is None
    assert short_metrics["mfe_price"] == 0.0
    assert short_metrics["bars_to_mfe"] == 0
    assert short_metrics["capture_ratio"] is None


def test_first_occurrence_wins_for_tied_mfe_and_mae() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=104.0,
        entry_idx=0,
        exit_idx=3,
        high=_series([101.0, 110.0, 110.0, 105.0]),
        low=_series([99.0, 98.0, 98.0, 103.0]),
    )

    assert metrics["bars_to_mfe"] == 1
    assert metrics["bars_to_mae"] == 1


def test_atr_fields_are_null_without_explicit_positive_atr_series() -> None:
    no_atr = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=106.0,
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 110.0]),
        low=_series([99.0, 98.0]),
    )
    zero_atr = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=106.0,
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 110.0]),
        low=_series([99.0, 98.0]),
        diagnostic_atr_series=_series([0.0, 2.0]),
    )

    for metrics in (no_atr, zero_atr):
        assert metrics["mfe_atr"] is None
        assert metrics["mae_atr"] is None
        assert metrics["captured_atr"] is None
        assert metrics["giveback_atr"] is None
        assert metrics["mfe_pct"] == 0.10


def test_exit_bar_is_included_for_bar_level_diagnostics() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=99.0,
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 110.0]),
        low=_series([99.5, 98.0]),
    )

    assert metrics["mfe_price"] == 10.0
    assert metrics["mae_price"] == 2.0
    assert metrics["bars_to_mfe"] == 1


def test_quality_flags_are_additive_for_signal_giveback_failure() -> None:
    record = {
        "direction": "long",
        "entry_price": 100.0,
        "exit_price": 101.0,
        "exit_reason": "signal:ema_cross",
        "exit_kind": "signal",
        "entry_context_state": "up",
    }
    diagnostics = build_trade_quality_diagnostics(
        record,
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 110.0]),
        low=_series([99.0, 98.0]),
    )

    assert "high_mfe_low_capture" in diagnostics["quality_flags"]
    assert "signal_exit_giveback_failure" in diagnostics["quality_flags"]
    assert "signal_exit_winner" not in diagnostics["quality_flags"]


def test_quality_flags_cover_winner_and_stop_loss_cases() -> None:
    signal_winner = build_trade_quality_diagnostics(
        {
            "direction": "long",
            "entry_price": 100.0,
            "exit_price": 108.0,
            "exit_reason": "signal:ema_cross",
            "exit_kind": "signal",
            "entry_context_state": "up",
        },
        entry_idx=0,
        exit_idx=1,
        high=_series([101.0, 110.0]),
        low=_series([99.0, 98.0]),
    )
    stop_loss = build_trade_quality_diagnostics(
        {
            "direction": "long",
            "entry_price": 100.0,
            "exit_price": 99.6,
            "exit_reason": "stop_loss:atr_sl",
            "exit_kind": "stop_loss",
            "entry_context_state": "neutral",
        },
        entry_idx=0,
        exit_idx=1,
        high=_series([100.2, 100.3]),
        low=_series([99.8, 99.5]),
    )

    assert "high_mfe_high_capture" in signal_winner["quality_flags"]
    assert "signal_exit_winner" in signal_winner["quality_flags"]
    assert "stop_loss_after_low_mfe" in stop_loss["quality_flags"]
    assert "stop_loss_after_bad_context" in stop_loss["quality_flags"]


def test_quality_breakdowns_ignore_null_values_and_do_not_coerce_atr_to_zero() -> None:
    records = [
        {
            "status": "closed",
            "exit_reason": "signal:ema_cross",
            "exit_component_id": "ema_cross_loss_exit",
            "quality_flags": ["high_mfe_low_capture", "signal_exit_giveback_failure"],
            "mfe_pct": 0.05,
            "mfe_atr": None,
            "capture_ratio": 0.2,
            "giveback_pct": 0.04,
            "giveback_atr": None,
        },
        {
            "status": "closed",
            "exit_reason": "signal:ema_cross",
            "exit_component_id": "ema_cross_loss_exit",
            "quality_flags": ["high_mfe_low_capture"],
            "mfe_pct": 0.03,
            "mfe_atr": None,
            "capture_ratio": None,
            "giveback_pct": 0.02,
            "giveback_atr": None,
        },
    ]

    by_flag = build_quality_flag_breakdown(records)
    assert by_flag["high_mfe_low_capture"]["trades"] == 2
    assert by_flag["high_mfe_low_capture"]["avg_mfe_atr"] is None
    assert by_flag["high_mfe_low_capture"]["avg_giveback_atr"] is None
    assert by_flag["high_mfe_low_capture"]["avg_mfe_pct"] == pytest.approx(0.04)
    assert by_flag["high_mfe_low_capture"]["avg_capture_ratio"] == 0.2

    by_component = build_exit_component_quality_breakdown(records)
    bucket = by_component["ema_cross_loss_exit"]
    assert bucket["avg_mfe_atr"] is None
    assert bucket["signal_exit_giveback_failures"] == 1
