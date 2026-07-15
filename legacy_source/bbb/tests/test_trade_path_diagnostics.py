"""Schema v6 trade path diagnostics (nested path_diagnostics + reference_levels)."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")

from research.strategies.ema_pullback.execution.exit_attribution import ExitAttributionContext
from research.strategies.ema_pullback.execution.results import build_trade_quality_breakdowns
from research.strategies.ema_pullback.execution.trade_analyzer import (
    _compute_reference_levels,
    build_path_diagnostics_summary,
    build_trade_quality_diagnostics,
    compute_trade_quality_metrics,
)


def _series(values: list[float], *, start: str = "2024-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=idx)


def _record(**kwargs: object) -> dict[str, object]:
    base = {
        "direction": "long",
        "entry_price": 100.0,
        "exit_price": 106.0,
        "exit_reason": "signal:test",
        "exit_kind": "signal",
        "entry_context_state": "up",
        "entry_profile": "aligned",
    }
    base.update(kwargs)
    return base


def test_losing_long_positive_mfe_negative_capture_and_large_giveback() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=100.0,
        exit_price=95.0,
        entry_idx=0,
        exit_idx=2,
        high=_series([101.0, 108.0, 96.0]),
        low=_series([99.0, 97.0, 94.0]),
    )
    assert metrics["mfe_price"] == 8.0
    assert metrics["capture_ratio"] == pytest.approx(-0.625)
    assert metrics["giveback_price"] == 13.0
    assert metrics["giveback_pct"] == pytest.approx(0.13)


def test_zero_mfe_null_capture_and_giveback() -> None:
    metrics = compute_trade_quality_metrics(
        direction="long",
        entry_price=101.0,
        exit_price=100.0,
        entry_idx=0,
        exit_idx=0,
        high=_series([100.0]),
        low=_series([99.0]),
    )
    assert metrics["mfe_price"] == 0.0
    assert metrics["capture_ratio"] is None
    assert metrics["giveback_price"] is None
    assert metrics["giveback_pct"] is None


def test_flat_nested_parity_on_closed_trade() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    high = pd.Series([101.0, 110.0, 106.0], index=idx)
    low = pd.Series([99.0, 98.0, 103.0], index=idx)
    diagnostics = build_trade_quality_diagnostics(
        _record(),
        entry_idx=0,
        exit_idx=2,
        high=high,
        low=low,
        index=idx,
    )
    path = diagnostics["path_diagnostics"]
    assert diagnostics["mfe_price"] == path["mfe"]["price_move"]
    assert diagnostics["mfe_pct"] == path["mfe"]["pct"]
    assert diagnostics["mae_price"] == path["mae"]["price_move"]
    assert diagnostics["mae_pct"] == path["mae"]["pct"]
    assert diagnostics["capture_ratio"] == path["capture"]["capture_ratio"]
    assert diagnostics["captured_pct"] == path["capture"]["captured_pct"]
    assert diagnostics["giveback_price"] == path["capture"]["giveback_price"]
    assert diagnostics["giveback_pct"] == path["capture"]["giveback_pct"]
    assert diagnostics["bars_from_mfe_to_exit"] == path["capture"]["bars_from_mfe_to_exit"]
    assert diagnostics["bars_to_mfe"] == path["mfe"]["bars_from_entry"]
    assert diagnostics["bars_to_mae"] == path["mae"]["bars_from_entry"]


def test_short_winner_capture_and_giveback() -> None:
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
    assert metrics["capture_ratio"] == pytest.approx(0.8)
    assert metrics["giveback_price"] == 1.0
    assert metrics["giveback_pct"] == pytest.approx(0.01)


def _ctx_sl_tp(*, idx: pd.DatetimeIndex, sl: float, tp: float) -> ExitAttributionContext:
    sl_s = pd.Series(sl, index=idx, dtype=float)
    tp_s = pd.Series(tp, index=idx, dtype=float)
    return ExitAttributionContext(
        index=idx,
        instance_ids=("sl", "tp"),
        exit_kinds=("stop_loss", "take_profit"),
        long_signal_by_rule=(None, None),
        short_signal_by_rule=(None, None),
        distance_ratio_by_rule=(sl_s, tp_s),
        sl_stop_agg=sl_s,
        tp_stop_agg=tp_s,
    )


def test_reference_tp_before_sl_long() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    ctx = _ctx_sl_tp(idx=idx, sl=0.02, tp=0.05)
    ref = _compute_reference_levels(
        direction="long",
        entry_price=100.0,
        entry_idx=0,
        exit_idx=3,
        high=pd.Series([100.0, 105.0, 106.0, 104.0], index=idx),
        low=pd.Series([99.0, 99.5, 99.0, 98.0], index=idx),
        open_=pd.Series([100.0, 100.0, 105.0, 104.0], index=idx),
        close=pd.Series([100.0, 100.0, 100.0, 100.0], index=idx),
        attribution=ctx,
        profile="aligned",
        index=idx,
    )
    assert ref["reference_levels_available"] is True
    assert ref["initial_take_profit_price"] == pytest.approx(105.0)
    assert ref["initial_stop_price"] == pytest.approx(98.0)
    assert ref["first_level_hit"] == "take_profit"
    assert ref["reached_initial_tp"] is True
    assert ref["bars_to_first_level_hit"] == 1


def test_reference_sl_before_tp_long() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    ctx = _ctx_sl_tp(idx=idx, sl=0.02, tp=0.10)
    ref = _compute_reference_levels(
        direction="long",
        entry_price=100.0,
        entry_idx=0,
        exit_idx=2,
        high=pd.Series([100.0, 99.0, 100.0], index=idx),
        low=pd.Series([100.0, 97.0, 98.0], index=idx),
        open_=pd.Series([100.0, 99.0, 98.0], index=idx),
        close=pd.Series([100.0, 100.0, 100.0], index=idx),
        attribution=ctx,
        profile="aligned",
        index=idx,
    )
    assert ref["first_level_hit"] == "stop_loss"
    assert ref["reached_initial_sl"] is True
    assert ref["bars_to_first_level_hit"] == 1


def test_reference_ambiguous_same_bar() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    ctx = _ctx_sl_tp(idx=idx, sl=0.02, tp=0.05)
    ref = _compute_reference_levels(
        direction="long",
        entry_price=100.0,
        entry_idx=0,
        exit_idx=1,
        high=pd.Series([100.0, 106.0], index=idx),
        low=pd.Series([100.0, 97.0], index=idx),
        open_=pd.Series([100.0, 100.0], index=idx),
        close=pd.Series([100.0, 100.0], index=idx),
        attribution=ctx,
        profile="aligned",
        index=idx,
    )
    assert ref["first_level_hit"] == "ambiguous_same_bar"


def test_reference_available_but_untouched() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    ctx = _ctx_sl_tp(idx=idx, sl=0.02, tp=0.10)
    ref = _compute_reference_levels(
        direction="long",
        entry_price=100.0,
        entry_idx=0,
        exit_idx=2,
        high=pd.Series([100.0, 101.0, 102.0], index=idx),
        low=pd.Series([100.0, 99.5, 99.0], index=idx),
        open_=pd.Series([100.0, 100.0, 100.0], index=idx),
        close=pd.Series([100.0, 100.0, 100.0], index=idx),
        attribution=ctx,
        profile="aligned",
        index=idx,
    )
    assert ref["reference_levels_available"] is True
    assert ref["first_level_hit"] == "none"
    assert ref["reached_initial_tp"] is False
    assert ref["reached_initial_sl"] is False


def test_reference_unavailable_without_attribution() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    ref = _compute_reference_levels(
        direction="long",
        entry_price=100.0,
        entry_idx=0,
        exit_idx=1,
        high=pd.Series([101.0, 102.0], index=idx),
        low=pd.Series([99.0, 98.0], index=idx),
        open_=None,
        close=pd.Series([100.0, 100.0], index=idx),
        attribution=None,
        profile="aligned",
        index=idx,
    )
    assert ref["reference_levels_available"] is False


def test_path_diagnostics_summary_reference_hit_counts() -> None:
    records = [
        {
            "status": "closed",
            "direction": "long",
            "exit_reason": "signal:a",
            "mfe_pct": 0.05,
            "mae_pct": 0.02,
            "capture_ratio": 0.5,
            "giveback_pct": 0.01,
            "bars_to_mfe": 1,
            "bars_to_mae": 0,
            "path_diagnostics": {"mfe": {}, "mae": {}, "capture": {}},
            "reference_levels": {
                "reference_levels_available": True,
                "first_level_hit": "none",
            },
        },
        {
            "status": "closed",
            "direction": "short",
            "exit_reason": "stop_loss:sl",
            "mfe_pct": 0.03,
            "mae_pct": 0.01,
            "capture_ratio": None,
            "giveback_pct": None,
            "bars_to_mfe": 0,
            "bars_to_mae": 1,
            "path_diagnostics": {"mfe": {}, "mae": {}, "capture": {}},
            "reference_levels": {"reference_levels_available": False},
        },
    ]
    summary = build_path_diagnostics_summary(records)
    total = summary["total"]
    assert total["trade_count"] == 2
    assert total["reference_levels_available_count"] == 1
    assert total["reference_levels_unavailable_count"] == 1
    assert total["no_reference_level_hit_count"] == 1


def test_build_trade_quality_breakdowns_includes_path_summary() -> None:
    records = [
        {
            "status": "closed",
            "direction": "long",
            "exit_reason": "signal:a",
            "mfe_pct": 0.04,
            "mae_pct": 0.02,
            "capture_ratio": 0.6,
            "giveback_pct": 0.01,
            "bars_to_mfe": 1,
            "bars_to_mae": 0,
            "path_diagnostics": {"mfe": {}, "mae": {}, "capture": {}},
            "reference_levels": {"reference_levels_available": False},
        }
    ]
    breakdowns = build_trade_quality_breakdowns(records)
    assert "path_diagnostics_summary" in breakdowns
    assert breakdowns["path_diagnostics_summary"]["total"]["trade_count"] == 1


def test_bar_time_ms_datetime_index_matches_entry_time_ms() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    from research.strategies.ema_pullback.execution.trade_analyzer import _bar_time_ms

    assert _bar_time_ms(idx, 1) == int(idx[1].timestamp() * 1000)


def test_bar_time_ms_open_time_ms_integer_index() -> None:
    from research.strategies.ema_pullback.execution.trade_analyzer import _bar_time_ms

    ms_idx = pd.Index([1_704_067_200_000, 1_704_070_800_000])
    assert _bar_time_ms(ms_idx, 0) == 1_704_067_200_000
    assert _bar_time_ms(ms_idx, 1) == 1_704_070_800_000


@pytest.mark.optional_vectorbt
def test_reference_levels_inferred_from_entry_context_when_profile_missing() -> None:
    vbt = pytest.importorskip("vectorbt")
    from research.strategies.ema_pullback.execution.results import extract_trade_records

    idx = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    close = pd.Series(100.0, index=idx, dtype=float)
    high = close + 2.0
    low = close - 2.0
    open_ = close.copy()
    entries = pd.Series(False, index=idx)
    entries.iloc[2] = True
    exits = pd.Series(False, index=idx)
    exits.iloc[6] = True
    sl_ratio = pd.Series(0.02, index=idx)
    tp_ratio = pd.Series(0.05, index=idx)
    ctx = ExitAttributionContext(
        index=idx,
        instance_ids=("atr_sl", "atr_tp"),
        exit_kinds=("stop_loss", "take_profit"),
        long_signal_by_rule=(None, None),
        short_signal_by_rule=(None, None),
        distance_ratio_by_rule=(sl_ratio, tp_ratio),
        sl_stop_agg_by_profile={
            "aligned": sl_ratio,
            "countertrend": sl_ratio,
            "neutral": sl_ratio,
        },
        tp_stop_agg_by_profile={
            "aligned": tp_ratio,
            "countertrend": tp_ratio,
            "neutral": tp_ratio,
        },
        sl_stop_agg=sl_ratio,
        tp_stop_agg=tp_ratio,
    )
    pf = vbt.Portfolio.from_signals(close, entries, exits, freq="1h")
    context_state = pd.Series("up", index=idx, dtype=object)
    rec = extract_trade_records(
        pf,
        close,
        high=high,
        low=low,
        open_s=open_,
        attribution=ctx,
        context_state=context_state,
    )[0]
    assert rec["entry_context_state"] == "up"
    assert rec.get("entry_profile") is None
    assert rec["reference_levels"]["reference_levels_available"] is True


@pytest.mark.optional_vectorbt
def test_open_trade_omits_nested_sections() -> None:
    vbt = pytest.importorskip("vectorbt")

    idx = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx)
    high = pd.Series([1.2, 2.2, 3.5, 4.5, 5.2], index=idx)
    low = pd.Series([0.8, 1.8, 2.5, 3.5, 4.8], index=idx)
    entries = pd.Series([False, True, False, False, False], index=idx)
    exits_open = pd.Series([False, False, False, False, False], index=idx)
    pf = vbt.Portfolio.from_signals(close, entries, exits_open, freq="1h")
    from research.strategies.ema_pullback.execution.results import extract_trade_records

    record = extract_trade_records(pf, close, high=high, low=low)[0]
    assert record["status"] == "open"
    assert "path_diagnostics" not in record
    assert "reference_levels" not in record
    assert "mfe_price" not in record
