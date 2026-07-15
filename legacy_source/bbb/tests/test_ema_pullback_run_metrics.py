"""Tests for ema_pullback run helpers (no vectorbt)."""

from __future__ import annotations

from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("pandas")

import pandas as pd

from research.strategies.ema_pullback.component_builders import (
    exit_policy,
    exit_rsi,
    trade_management,
)
from research.strategies.ema_pullback.execution import backtest
from research.strategies.ema_pullback.execution.backtest import build_trade_side_metrics, ensure_finite_metric
from research.strategies.ema_pullback.execution.results import build_bounce_counter_breakdown
from research.strategies.ema_pullback.execution.exits import PortfolioExitOutputs
from research.strategies.ema_pullback.execution.report_table import print_comparison_table
from research.strategies.ema_pullback.execution.signals import PortfolioSignals
from research.strategies.ema_pullback.features.plan import FeaturePlan
from research.strategies.ema_pullback.spec_instances import (
    make_ema_pullback_strategy_spec,
)


def test_ensure_finite_metric_accepts_finite() -> None:
    assert ensure_finite_metric("sharpe_ratio", 0.0) == 0.0
    assert ensure_finite_metric("profit_factor", 1.25) == 1.25
    assert ensure_finite_metric("max_drawdown", -0.5) == -0.5


def test_ensure_finite_metric_rejects_nan() -> None:
    assert ensure_finite_metric("sharpe_ratio", float("nan")) == 0.0


def test_ensure_finite_metric_rejects_inf() -> None:
    assert ensure_finite_metric("max_drawdown", float("inf")) == 0.0


def test_bounce_counter_breakdown_groups_closed_trades_by_side_and_bounce() -> None:
    records = [
        {
            "status": "closed",
            "direction": "long",
            "pnl": 10.0,
            "gross_pnl": 11.0,
            "fees_paid": 1.0,
            "return_pct": 0.1,
            "hold_bars": 2,
            "entry_bounce_counter_side": "long",
            "entry_effective_bounce_number": 1,
        },
        {
            "status": "closed",
            "direction": "long",
            "pnl": -5.0,
            "gross_pnl": -4.0,
            "fees_paid": 1.0,
            "return_pct": -0.05,
            "hold_bars": 3,
            "entry_bounce_counter_side": "long",
            "entry_effective_bounce_number": 2,
        },
        {
            "status": "open",
            "direction": "short",
            "entry_bounce_counter_side": "short",
            "entry_effective_bounce_number": 1,
        },
    ]

    breakdown = build_bounce_counter_breakdown(records)

    assert breakdown is not None
    assert breakdown["long"]["1"]["trades"] == 1
    assert breakdown["long"]["2"]["trades"] == 1
    assert breakdown["short"]["total"]["trades"] == 0
    assert breakdown["total"]["trades"] == 2


def test_comparison_table_includes_side_and_total_columns(capsys: pytest.CaptureFixture[str]) -> None:
    print_comparison_table(
        [
            {
                "variant": "v",
                "config_id": "cid",
                "fast": 20,
                "anchor": 200,
                "slow": 1000,
                "long_trades": 2,
                "long_pnl": 10.0,
                "long_return_pct": 0.1,
                "long_profit_factor": 2.0,
                "long_win_rate": 0.5,
                "short_trades": 0,
                "short_pnl": 0.0,
                "short_return_pct": 0.0,
                "short_profit_factor": None,
                "short_win_rate": None,
                "total_trades": 2,
                "total_pnl": 10.0,
                "total_return_pct": 0.1,
                "total_profit_factor": 2.0,
                "total_win_rate": 0.5,
                "total_sharpe": 0.1,
                "total_max_drawdown": -0.2,
                "open_trades_long": 0,
                "open_trades_short": 1,
                "open_trades_total": 1,
            }
        ]
    )
    out = capsys.readouterr().out
    assert "long_trades" in out
    assert "short_trades" in out
    assert "total_trades" in out
    assert "total_sharpe" in out
    assert "open_trades_total" in out
    assert "null" in out
    assert "fast" in out
    assert "anchor" in out
    assert "slow" in out


def test_build_trade_side_metrics_aggregates_normalized_records() -> None:
    metrics = build_trade_side_metrics(
        [
            {"direction": "long", "status": "closed", "pnl": 30.0},
            {"direction": "long", "status": "closed", "pnl": -10.0},
        ],
        init_cash=100.0,
        sharpe=0.5,
        max_drawdown=-0.1,
    )

    assert metrics.long.trades == 2
    assert metrics.long.pnl == 20.0
    assert metrics.long.return_pct == 0.2
    assert metrics.long.profit_factor == 3.0
    assert metrics.long.win_rate == 0.5
    assert metrics.short.trades == 0
    assert metrics.short.pnl == 0.0
    assert metrics.short.return_pct == 0.0
    assert metrics.short.profit_factor is None
    assert metrics.short.win_rate is None
    assert metrics.total.trades == 2
    assert metrics.total.pnl == 20.0
    assert metrics.total.return_pct == 0.2
    assert metrics.sharpe == 0.5
    assert metrics.max_drawdown == -0.1
    assert metrics.open_trades.total == 0


def test_build_trade_side_metrics_non_finite_profit_factor_is_null() -> None:
    metrics = build_trade_side_metrics(
        [{"direction": "long", "status": "closed", "pnl": 5.0}],
        init_cash=100.0,
        sharpe=0.0,
        max_drawdown=0.0,
    )

    assert metrics.long.profit_factor is None
    assert metrics.long.win_rate == 1.0
    assert metrics.total.profit_factor is None


def test_build_trade_side_metrics_ignores_open_trades_for_realized() -> None:
    metrics = build_trade_side_metrics(
        [
            {"direction": "long", "status": "closed", "pnl": 10.0},
            {"direction": "long", "status": "open", "pnl": 999.0},
            {"direction": "short", "status": "open", "pnl": -500.0},
        ],
        init_cash=100.0,
        sharpe=0.0,
        max_drawdown=0.0,
    )

    assert metrics.long.trades == 1
    assert metrics.long.pnl == 10.0
    assert metrics.total.pnl == 10.0
    assert metrics.open_trades.long == 1
    assert metrics.open_trades.short == 1
    assert metrics.open_trades.total == 2


@pytest.mark.parametrize(
    ("sl_values", "tp_values", "expected_entries"),
    [
        pytest.param(
            [float("nan"), 0.01, 0.01, 0.01],
            [float("nan")] * 4,
            [False, True, True, True],
            id="only_sl",
        ),
        pytest.param(
            [float("nan")] * 4,
            [float("nan"), 0.02, 0.02, 0.02],
            [False, True, True, True],
            id="only_tp",
        ),
        pytest.param(
            [float("nan"), 0.01, 0.01, 0.01],
            [float("nan"), 0.02, 0.02, 0.02],
            [False, True, True, True],
            id="sl_and_tp",
        ),
        pytest.param(
            [float("nan")] * 4,
            [float("nan")] * 4,
            [True, True, True, True],
            id="signal_only",
        ),
        pytest.param(
            [float("nan"), 0.01, 0.01, 0.01],
            [float("nan")] * 4,
            [False, True, True, True],
            id="rsi_plus_sl",
        ),
        pytest.param(
            [float("nan")] * 4,
            [float("nan"), 0.02, 0.02, 0.02],
            [False, True, True, True],
            id="rsi_plus_tp",
        ),
    ],
)
def test_run_strategy_spec_wires_short_signals_and_masks_warmup(
    monkeypatch: pytest.MonkeyPatch,
    sl_values: list[float],
    tp_values: list[float],
    expected_entries: list[bool],
) -> None:
    captured: dict[str, object] = {}

    class FakeTrades:
        records = None

        def count(self) -> int:
            return 0

        def profit_factor(self) -> float:
            return 1.0

    class FakePortfolio:
        trades = FakeTrades()

        def sharpe_ratio(self) -> float:
            return 0.0

        def max_drawdown(self) -> float:
            return 0.0

    class FakePortfolioFactory:
        @staticmethod
        def from_signals(close: pd.Series, **kwargs: object) -> FakePortfolio:
            captured["close"] = close
            captured.update(kwargs)
            return FakePortfolio()

    monkeypatch.setitem(sys.modules, "vectorbt", SimpleNamespace(Portfolio=FakePortfolioFactory))

    def fake_build_signals_from_spec(
        df: pd.DataFrame, spec: object, plan: object, *, context_bundle: object = None
    ) -> PortfolioSignals:
        values = pd.Series([True, True, True, True], index=df.index, dtype=bool)
        return PortfolioSignals(
            entries=values,
            short_entries=values,
        )

    def fake_build_exit_outputs_from_spec(
        df: pd.DataFrame,
        spec: object,
        plan: object,
        *,
        context_bundle: object = None,
    ) -> PortfolioExitOutputs:
        exits = pd.Series(False, index=df.index, dtype=bool)
        sl_stop = pd.Series(sl_values, index=df.index)
        tp_stop = pd.Series(tp_values, index=df.index)
        nan_s = pd.Series(float("nan"), index=df.index, dtype=float)
        neutral = pd.Series("neutral", index=df.index, dtype="object")
        profiles = {
            "aligned": exits.copy(),
            "countertrend": exits.copy(),
            "neutral": exits.copy(),
        }
        sl_profiles = {"aligned": sl_stop.astype(float), "countertrend": sl_stop.astype(float), "neutral": nan_s}
        tp_profiles = {"aligned": tp_stop.astype(float), "countertrend": tp_stop.astype(float), "neutral": nan_s}
        return PortfolioExitOutputs(
            exits=exits,
            short_exits=exits,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            stop_ready_long=pd.Series(expected_entries, index=df.index, dtype=bool),
            stop_ready_short=pd.Series(expected_entries, index=df.index, dtype=bool),
            context_state=neutral,
            profile_long=neutral,
            profile_short=neutral,
            long_exits_by_profile=profiles,
            short_exits_by_profile=profiles,
            sl_stop_by_profile=sl_profiles,
            tp_stop_by_profile=tp_profiles,
        )

    monkeypatch.setattr(backtest, "build_signals_from_spec", fake_build_signals_from_spec)
    monkeypatch.setattr(backtest, "build_exit_outputs_from_spec", fake_build_exit_outputs_from_spec)

    idx = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    close = pd.Series([100.0, 101.0, 102.0, 103.0], index=idx)
    ohlcv = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )

    backtest.run_strategy_spec(make_ema_pullback_strategy_spec(), ohlcv)

    # signal_args packs entries/short_entries/exits matrices/profile ids for callback mode.
    signal_args = captured["signal_args"]
    assert isinstance(signal_args, tuple)
    assert signal_args[0].tolist() == expected_entries
    assert signal_args[1].tolist() == expected_entries
    assert signal_args[2].shape == (4, 3)
    assert signal_args[3].shape == (4, 3)
    assert not signal_args[2].any()
    assert not signal_args[3].any()
    # Step 15: OHLC passed into vectorbt for stop semantics (regression guard vs close-only).
    pd.testing.assert_series_equal(captured["open"], ohlcv["open"].astype(float), check_names=False)
    pd.testing.assert_series_equal(captured["high"], ohlcv["high"].astype(float), check_names=False)
    pd.testing.assert_series_equal(captured["low"], ohlcv["low"].astype(float), check_names=False)
    pd.testing.assert_series_equal(captured["close"], ohlcv["close"].astype(float), check_names=False)


def test_run_strategy_spec_raises_when_ohlc_column_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeTrades:
        records = None

        def count(self) -> int:
            return 0

        def profit_factor(self) -> float:
            return 1.0

    class FakePortfolio:
        trades = FakeTrades()

        def sharpe_ratio(self) -> float:
            return 0.0

        def max_drawdown(self) -> float:
            return 0.0

    class FakePortfolioFactory:
        @staticmethod
        def from_signals(close: pd.Series, **kwargs: object) -> FakePortfolio:
            captured.update(kwargs)
            return FakePortfolio()

    monkeypatch.setitem(sys.modules, "vectorbt", SimpleNamespace(Portfolio=FakePortfolioFactory))

    def fake_build_signals_from_spec(
        df: pd.DataFrame, spec: object, plan: object, *, context_bundle: object = None
    ) -> PortfolioSignals:
        values = pd.Series([True, True, True, True], index=df.index, dtype=bool)
        return PortfolioSignals(entries=values, short_entries=values)

    def fake_build_exit_outputs_from_spec(
        df: pd.DataFrame,
        spec: object,
        plan: object,
        *,
        context_bundle: object = None,
    ) -> PortfolioExitOutputs:
        idx = df.index
        nan4 = [float("nan")] * 4
        neutral = pd.Series("neutral", index=idx, dtype="object")
        false_s = pd.Series(False, index=idx, dtype=bool)
        nan_s = pd.Series(float("nan"), index=idx, dtype=float)
        return PortfolioExitOutputs(
            exits=false_s,
            short_exits=false_s,
            sl_stop=pd.Series(nan4, index=idx),
            tp_stop=pd.Series(nan4, index=idx),
            stop_ready_long=pd.Series(True, index=idx, dtype=bool),
            stop_ready_short=pd.Series(True, index=idx, dtype=bool),
            context_state=neutral,
            profile_long=neutral,
            profile_short=neutral,
            long_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            short_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            sl_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
            tp_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
        )

    monkeypatch.setattr(backtest, "build_signals_from_spec", fake_build_signals_from_spec)
    monkeypatch.setattr(backtest, "build_exit_outputs_from_spec", fake_build_exit_outputs_from_spec)
    monkeypatch.setattr(backtest, "add_feature_columns_from_plan", lambda ohlcv, plan: ohlcv)

    idx = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    close = pd.Series([100.0, 101.0, 102.0, 103.0], index=idx)
    ohlcv = pd.DataFrame(
        {
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )

    with pytest.raises(SystemExit, match="open.*high.*low|missing"):
        backtest.run_strategy_spec(make_ema_pullback_strategy_spec(), ohlcv)

    assert not captured, "Portfolio.from_signals must not run when OHLC columns are missing"


@pytest.mark.optional_vectorbt
def test_run_strategy_spec_accepts_signal_only_exits_with_nan_stops() -> None:
    pytest.importorskip("vectorbt")
    spec = make_ema_pullback_strategy_spec(
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy(
                always_on=(
                    exit_rsi(
                        instance_id="rsi_signal_only",
                        timeframe="base",
                        period=14,
                        long_exit_above=70.0,
                        short_exit_below=30.0,
                    ),
                ),
                aligned=(),
                countertrend=(),
                neutral=(),
            )
        )
    )
    idx = pd.date_range("2024-01-01", periods=40, freq="h", tz="UTC")
    close = pd.Series([100.0 + float(i % 7) for i in range(len(idx))], index=idx)
    ohlcv = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )

    result = backtest.run_strategy_spec(spec, ohlcv)

    assert result.variant == spec.variant


@pytest.mark.optional_vectorbt
def test_entry_lock_distance_uses_entry_profile_distance(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("vectorbt")
    idx = pd.date_range("2024-01-01", periods=8, freq="h", tz="UTC")
    close = pd.Series([100.0] * len(idx), index=idx)
    ohlcv = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    ohlcv.loc[idx[4], "low"] = 98.5  # hits tight 1% stop, not wide 10%

    plan = FeaturePlan(
        features=(),
        anchor_columns={"fast": "ema_fast", "anchor": "ema_anchor", "slow": "ema_slow"},
        exit_distance_columns={},
        rsi_columns={},
        htf_context_columns_by_ref={},
    )

    def fake_plan(_spec: object) -> FeaturePlan:
        return plan

    def fake_features(df: pd.DataFrame, _plan: FeaturePlan) -> pd.DataFrame:
        out = df.copy()
        out["ema_fast"] = out["close"]
        out["ema_anchor"] = out["close"]
        out["ema_slow"] = out["close"]
        return out

    def fake_signals(
        df: pd.DataFrame, _spec: object, _plan: object, *, context_bundle: object = None
    ) -> PortfolioSignals:
        entries = pd.Series(False, index=df.index, dtype=bool)
        entries.iloc[1] = True
        return PortfolioSignals(entries=entries, short_entries=pd.Series(False, index=df.index, dtype=bool))

    def fake_exits(
        df: pd.DataFrame, _spec: object, _plan: object, *, context_bundle: object = None
    ) -> PortfolioExitOutputs:
        false_s = pd.Series(False, index=df.index, dtype=bool)
        nan_s = pd.Series(float("nan"), index=df.index, dtype=float)
        sl_aligned = pd.Series(0.10, index=df.index, dtype=float)
        sl_counter = pd.Series(0.01, index=df.index, dtype=float)
        tp_all = pd.Series(float("nan"), index=df.index, dtype=float)
        profile = pd.Series("aligned", index=df.index, dtype="object")
        profile.iloc[3:] = "countertrend"  # flips after entry, must not affect distance
        return PortfolioExitOutputs(
            exits=false_s,
            short_exits=false_s,
            sl_stop=sl_aligned,
            tp_stop=tp_all,
            stop_ready_long=pd.Series(True, index=df.index, dtype=bool),
            stop_ready_short=pd.Series(True, index=df.index, dtype=bool),
            context_state=pd.Series("neutral", index=df.index, dtype="object"),
            profile_long=profile,
            profile_short=pd.Series("neutral", index=df.index, dtype="object"),
            long_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            short_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            sl_stop_by_profile={"aligned": sl_aligned, "countertrend": sl_counter, "neutral": nan_s},
            tp_stop_by_profile={"aligned": tp_all, "countertrend": tp_all, "neutral": tp_all},
        )

    monkeypatch.setattr(backtest, "build_feature_plan_from_strategy_spec", fake_plan)
    monkeypatch.setattr(backtest, "add_feature_columns_from_plan", fake_features)
    monkeypatch.setattr(backtest, "build_signals_from_spec", fake_signals)
    monkeypatch.setattr(backtest, "build_exit_outputs_from_spec", fake_exits)

    result = backtest.run_strategy_spec(make_ema_pullback_strategy_spec(), ohlcv)
    assert result.trade_records[0]["status"] == "open"


@pytest.mark.optional_vectorbt
def test_entry_lock_signal_ignores_inactive_profile_and_honors_always_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("vectorbt")
    idx = pd.date_range("2024-01-01", periods=8, freq="h", tz="UTC")
    close = pd.Series([100.0] * len(idx), index=idx)
    ohlcv = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    plan = FeaturePlan(
        features=(),
        anchor_columns={"fast": "ema_fast", "anchor": "ema_anchor", "slow": "ema_slow"},
        exit_distance_columns={},
        rsi_columns={},
        htf_context_columns_by_ref={},
    )

    def fake_plan(_spec: object) -> FeaturePlan:
        return plan

    def fake_features(df: pd.DataFrame, _plan: FeaturePlan) -> pd.DataFrame:
        out = df.copy()
        out["ema_fast"] = out["close"]
        out["ema_anchor"] = out["close"]
        out["ema_slow"] = out["close"]
        return out

    def fake_signals(
        df: pd.DataFrame, _spec: object, _plan: object, *, context_bundle: object = None
    ) -> PortfolioSignals:
        entries = pd.Series(False, index=df.index, dtype=bool)
        entries.iloc[1] = True
        return PortfolioSignals(entries=entries, short_entries=pd.Series(False, index=df.index, dtype=bool))

    def fake_exits(
        df: pd.DataFrame, _spec: object, _plan: object, *, context_bundle: object = None
    ) -> PortfolioExitOutputs:
        false_s = pd.Series(False, index=df.index, dtype=bool)
        nan_s = pd.Series(float("nan"), index=df.index, dtype=float)
        aligned = false_s.copy()
        counter = false_s.copy()
        neutral = false_s.copy()
        counter.iloc[3] = True  # inactive after entry-lock
        aligned.iloc[5] = True  # active profile signal
        always_on_hit = false_s.copy()
        always_on_hit.iloc[6] = True
        profile = pd.Series("aligned", index=df.index, dtype="object")
        profile.iloc[2:] = "countertrend"
        long_by_profile = {
            "aligned": aligned | always_on_hit,
            "countertrend": counter | always_on_hit,
            "neutral": neutral | always_on_hit,
        }
        return PortfolioExitOutputs(
            exits=long_by_profile["aligned"],
            short_exits=false_s,
            sl_stop=nan_s,
            tp_stop=nan_s,
            stop_ready_long=pd.Series(True, index=df.index, dtype=bool),
            stop_ready_short=pd.Series(True, index=df.index, dtype=bool),
            context_state=pd.Series("neutral", index=df.index, dtype="object"),
            profile_long=profile,
            profile_short=pd.Series("neutral", index=df.index, dtype="object"),
            long_exits_by_profile=long_by_profile,
            short_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            sl_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
            tp_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
        )

    monkeypatch.setattr(backtest, "build_feature_plan_from_strategy_spec", fake_plan)
    monkeypatch.setattr(backtest, "add_feature_columns_from_plan", fake_features)
    monkeypatch.setattr(backtest, "build_signals_from_spec", fake_signals)
    monkeypatch.setattr(backtest, "build_exit_outputs_from_spec", fake_exits)

    result = backtest.run_strategy_spec(make_ema_pullback_strategy_spec(), ohlcv)
    assert result.trade_records[0]["exit_time_ms"] == int(idx[5].timestamp() * 1000)
