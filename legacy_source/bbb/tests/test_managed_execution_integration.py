"""Slice 4: execution-layer integration with managed exit provider."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from research.strategies.ema_pullback.execution import backtest
from research.strategies.ema_pullback.execution.exit_attribution import ExitAttributionContext
from research.strategies.ema_pullback.execution.exit_policy_candidates import (
    collect_exit_policy_bar_candidates,
)
from research.strategies.ema_pullback.execution.exits import PortfolioExitOutputs
from research.strategies.ema_pullback.execution.managed_components.take import (
    ACTIVE_TAKE_PROFILE_DISABLE_INITIAL_TP,
    normalize_take_profile_action,
)
from research.strategies.ema_pullback.execution.managed_execution_loop import (
    run_managed_execution_loop,
)
from research.strategies.ema_pullback.execution.managed_exit_provider import ManagedExitProvider
from research.strategies.ema_pullback.execution.trade_runtime import (
    ActiveManagementSnapshot,
    empty_active_management_snapshot,
)
from research.experiments.config_loader import load_strategy_config
from research.strategies.ema_pullback.spec import (
    BreakEvenStopParamsSpec,
    ExitManagementSpec,
    ManagementActivateWhenSpec,
    StopManagementRuleSpec,
    TakeManagementRuleSpec,
    TakeProfileSwitchParamsSpec,
    empty_exit_management,
)
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
from tests.phase_rule_test_helpers import make_phase_rule


def _series(values: list[float]) -> pd.Series:
    return pd.Series(
        values,
        index=pd.date_range("2024-01-01", periods=len(values), freq="h", tz="UTC"),
        dtype=float,
    )


def _false_series(n: int, index: pd.Index | None = None) -> pd.Series:
    idx = index if index is not None else _series([0.0] * n).index
    return pd.Series(False, index=idx, dtype=bool)


def _minimal_exit_outputs(
    n: int,
    *,
    sl_ratio: float = 0.10,
    tp_ratio: float = 0.20,
    profile: str = "neutral",
) -> PortfolioExitOutputs:
    idx = _series([0.0] * n).index
    sl_agg = pd.Series(sl_ratio, index=idx, dtype=float)
    tp_agg = pd.Series(tp_ratio, index=idx, dtype=float)
    profile_series = pd.Series(profile, index=idx, dtype=object)
    ctx = ExitAttributionContext(
        index=idx,
        instance_ids=("atr_sl", "atr_tp"),
        exit_kinds=("stop_loss", "take_profit"),
        long_signal_by_rule=(None, None),
        short_signal_by_rule=(None, None),
        distance_ratio_by_rule=(sl_agg, tp_agg),
        rule_groups=("always_on", "always_on"),
        sl_stop_agg_by_profile={profile: sl_agg},
        tp_stop_agg_by_profile={profile: tp_agg},
    )
    return PortfolioExitOutputs(
        exits=_false_series(n, idx),
        short_exits=_false_series(n, idx),
        sl_stop=sl_agg,
        tp_stop=tp_agg,
        stop_ready_long=pd.Series(True, index=idx, dtype=bool),
        stop_ready_short=pd.Series(True, index=idx, dtype=bool),
        context_state=profile_series,
        profile_long=profile_series,
        profile_short=profile_series,
        long_exits_by_profile={profile: _false_series(n, idx)},
        short_exits_by_profile={profile: _false_series(n, idx)},
        attribution=ctx,
    )


def _managed_be_spec() -> object:
    base = make_ema_pullback_strategy_spec(enabled_sides=("long",))
    exit_management = ExitManagementSpec(
        mode="managed",
        phase_rules=(
            make_phase_rule(
                "to_protected",
                "protected",
                "bars_in_trade",
                {"threshold": 1},
            ),
        ),
        stop_management=(
            StopManagementRuleSpec(
                rule_id="be",
                component_id="break_even_stop",
                activate_when=ManagementActivateWhenSpec(phase_at_least="protected"),
                params=BreakEvenStopParamsSpec(buffer_type="none", buffer=0.0),
            ),
        ),
        take_management=(),
        runtime_exits=(),
    )
    return replace(
        base,
        trade_management=replace(base.trade_management, exit_management=exit_management),
    )


def _managed_empty_spec() -> object:
    base = make_ema_pullback_strategy_spec(enabled_sides=("long",))
    exit_management = ExitManagementSpec(
        mode="managed",
        phase_rules=(
            make_phase_rule(
                "to_proven",
                "proven",
                "bars_in_trade",
                {"threshold": 2},
            ),
        ),
        stop_management=(),
        take_management=(),
        runtime_exits=(),
    )
    return replace(
        base,
        trade_management=replace(base.trade_management, exit_management=exit_management),
    )


def test_managed_be_closes_on_bar_n_plus_1_not_phase_bar() -> None:
    """BE armed at end of bar 0; low hits BE on bar 1 only."""
    spec = _managed_be_spec()
    n = 4
    close = _series([100.0, 101.0, 99.0, 100.0])
    open_ = _series([100.0, 101.0, 99.5, 100.0])
    high = _series([101.0, 102.0, 100.0, 101.0])
    low = _series([99.5, 101.5, 98.5, 99.5])
    entries = pd.Series([True, False, False, False], index=close.index, dtype=bool)
    short_entries = _false_series(n, close.index)
    exit_outputs = _minimal_exit_outputs(n)
    provider = ManagedExitProvider(
        phase_rules=spec.trade_management.exit_management.phase_rules,
        stop_management=spec.trade_management.exit_management.stop_management,
        take_management=(),
        runtime_exits=(),
    )
    result = run_managed_execution_loop(
        spec=spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=short_entries,
        exit_outputs=exit_outputs,
        provider=provider,
    )
    closed = [item for item in result.closed if not item.get("open")]
    assert len(closed) == 1
    assert closed[0]["exit_idx"] == 2
    assert closed[0]["exit_layer"] == "exit_management.stop_rule"
    assert closed[0]["winner"].candidate_type == "managed_stop"
    stop_events = [
        e for e in result.events if e.event_type == "active_stop_updated"
    ]
    assert len(stop_events) == 1
    assert stop_events[0].bar_index == 1
    assert stop_events[0].metadata.get("effective_from_bar") == 2


def test_managed_be_differs_from_empty_managed_on_fixture() -> None:
    n = 5
    close = _series([100.0, 101.0, 99.0, 100.0, 95.0])
    open_ = _series([100.0, 101.0, 99.5, 100.0, 96.0])
    high = _series([101.0, 102.0, 100.0, 101.0, 97.0])
    low = _series([99.5, 101.5, 98.5, 99.5, 89.0])
    entries = pd.Series([True, False, False, False, False], index=close.index, dtype=bool)
    short_entries = _false_series(n, close.index)
    exit_outputs = _minimal_exit_outputs(n)

    be_spec = _managed_be_spec()
    be_provider = ManagedExitProvider(
        phase_rules=be_spec.trade_management.exit_management.phase_rules,
        stop_management=be_spec.trade_management.exit_management.stop_management,
        take_management=(),
        runtime_exits=(),
    )
    be_result = run_managed_execution_loop(
        spec=be_spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=short_entries,
        exit_outputs=exit_outputs,
        provider=be_provider,
    )

    empty_spec = _managed_empty_spec()
    empty_provider = ManagedExitProvider(
        phase_rules=empty_spec.trade_management.exit_management.phase_rules,
        stop_management=(),
        take_management=(),
        runtime_exits=(),
    )
    empty_result = run_managed_execution_loop(
        spec=empty_spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=short_entries,
        exit_outputs=exit_outputs,
        provider=empty_provider,
    )

    be_closed = [item for item in be_result.closed if not item.get("open")]
    empty_closed = [item for item in empty_result.closed if not item.get("open")]
    assert be_closed[0]["exit_idx"] != empty_closed[0]["exit_idx"]


def test_execution_opens_from_precomputed_entries() -> None:
    spec = _managed_empty_spec()
    n = 3
    close = _series([100.0, 101.0, 102.0])
    open_ = close - 0.1
    high = close + 0.5
    low = close - 0.5
    entries = pd.Series([True, False, False], index=close.index, dtype=bool)
    short_entries = _false_series(n, close.index)
    provider = ManagedExitProvider(
        phase_rules=spec.trade_management.exit_management.phase_rules,
        stop_management=(),
        take_management=(),
        runtime_exits=(),
    )
    result = run_managed_execution_loop(
        spec=spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=short_entries,
        exit_outputs=_minimal_exit_outputs(n),
        provider=provider,
    )
    assert any(item.get("entry_idx") == 0 for item in result.closed)


def test_provider_bar_open_only_when_position_open_at_bar_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bar_open_indices: list[int] = []
    original = ManagedExitProvider.get_bar_open_candidates

    def _track_bar_open(
        self: ManagedExitProvider,
        inherited: object,
        *,
        bar_idx: int,
        **kwargs: object,
    ) -> list[object]:
        bar_open_indices.append(bar_idx)
        return original(self, inherited, bar_idx=bar_idx, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ManagedExitProvider, "get_bar_open_candidates", _track_bar_open)

    spec = _managed_be_spec()
    n = 3
    close = _series([100.0, 101.0, 102.0])
    open_ = close - 0.1
    high = close + 0.5
    low = close - 0.5
    entries = pd.Series([True, False, False], index=close.index, dtype=bool)
    provider = ManagedExitProvider(
        phase_rules=spec.trade_management.exit_management.phase_rules,
        stop_management=spec.trade_management.exit_management.stop_management,
        take_management=(),
        runtime_exits=(),
    )
    run_managed_execution_loop(
        spec=spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=_false_series(n, close.index),
        exit_outputs=_minimal_exit_outputs(n),
        provider=provider,
    )
    assert 0 not in bar_open_indices
    assert bar_open_indices == [1, 2]


def test_no_same_bar_reentry_after_close() -> None:
    from research.strategies.ema_pullback.spec import (
        PhaseRuntimeExitParamsSpec,
        RuntimeExitRuleSpec,
    )

    spec = _managed_be_spec()
    exit_management = replace(
        spec.trade_management.exit_management,
        phase_rules=(
            make_phase_rule(
                "to_exhaustion",
                "exhaustion",
                "bars_in_trade",
                {"threshold": 1},
            ),
        ),
        stop_management=(),
        runtime_exits=(
            RuntimeExitRuleSpec(
                rule_id="exit_ex",
                component_id="phase_runtime_exit",
                role="exit_management.runtime_exit",
                activate_when=ManagementActivateWhenSpec(phase_at_least="exhaustion"),
                exit_kind="market_close",
                params=PhaseRuntimeExitParamsSpec(exit_price="close"),
            ),
        ),
    )
    spec = replace(
        spec,
        trade_management=replace(spec.trade_management, exit_management=exit_management),
    )
    n = 3
    close = _series([100.0, 101.0, 102.0])
    open_ = close - 0.1
    high = close + 0.5
    low = close - 0.5
    entries = pd.Series([True, True, False], index=close.index, dtype=bool)
    short_entries = _false_series(n, close.index)
    provider = ManagedExitProvider(
        phase_rules=exit_management.phase_rules,
        stop_management=(),
        take_management=(),
        runtime_exits=exit_management.runtime_exits,
    )
    result = run_managed_execution_loop(
        spec=spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=short_entries,
        exit_outputs=_minimal_exit_outputs(n, tp_ratio=0.50),
        provider=provider,
    )
    closed = [item for item in result.closed if not item.get("open")]
    assert len(closed) == 1
    assert closed[0]["entry_idx"] == 0
    assert closed[0]["exit_idx"] == 2


@pytest.mark.optional_vectorbt
def test_diagnostic_only_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("vectorbt")

    def _integration_must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("execution integration must not run for diagnostic_only")

    monkeypatch.setattr(backtest, "run_managed_execution_loop", _integration_must_not_run)

    base = make_ema_pullback_strategy_spec()
    empty = empty_exit_management()
    diagnostic = replace(
        base,
        trade_management=replace(
            base.trade_management,
            exit_management=replace(
                empty,
                mode="diagnostic_only",
                phase_rules=(
                    make_phase_rule(
                        "to_proven",
                        "proven",
                        "bars_in_trade",
                        {"threshold": 2},
                    ),
                ),
            ),
        ),
    )
    idx = pd.date_range("2024-01-01", periods=120, freq="h", tz="UTC")
    close = pd.Series(range(100, 220), index=idx, dtype=float)
    data = pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0,
        }
    )
    result = backtest.run_strategy_spec(diagnostic, data)
    assert result.trade_records is not None


@pytest.mark.optional_vectorbt
def test_managed_empty_arrays_parity_unchanged() -> None:
    pytest.importorskip("vectorbt")
    from tests.test_trade_runtime_managed_core import (
        _managed_empty_exit_management,
        _ohlcv,
    )

    baseline = make_ema_pullback_strategy_spec()
    managed = replace(
        baseline,
        trade_management=replace(
            baseline.trade_management,
            exit_management=_managed_empty_exit_management(),
        ),
    )
    data = _ohlcv(120)
    baseline_result = backtest.run_strategy_spec(baseline, data)
    managed_result = backtest.run_strategy_spec(managed, data)
    assert managed_result.metrics.total.trades == baseline_result.metrics.total.trades
    assert managed_result.metrics.total.pnl == pytest.approx(baseline_result.metrics.total.pnl)


def test_disable_initial_tp_suppresses_tp_candidate_view_only() -> None:
    exit_outputs = _minimal_exit_outputs(3, tp_ratio=0.05)
    inherited = ActiveManagementSnapshot(
        active_take_profile=ACTIVE_TAKE_PROFILE_DISABLE_INITIAL_TP,
        active_take_rule_id="disable_tp",
        active_take_component_id="take_profile_switch",
    )
    candidates = collect_exit_policy_bar_candidates(
        bar_idx=1,
        direction="long",
        entry_idx=0,
        entry_price=100.0,
        locked_profile="neutral",
        open_=100.0,
        high=106.0,
        low=99.0,
        close=105.0,
        exit_outputs=exit_outputs,
        inherited_take_profile=inherited.active_take_profile,
        component_map=None,
    )
    types = {item.candidate_type for item in candidates}
    assert "take_profit" not in types


def test_disable_initial_tp_does_not_suppress_managed_stop() -> None:
    inherited = ActiveManagementSnapshot(
        active_stop_price=100.0,
        active_stop_rule_id="be",
        active_stop_component_id="break_even_stop",
        active_take_profile=ACTIVE_TAKE_PROFILE_DISABLE_INITIAL_TP,
        active_take_rule_id="disable_tp",
        active_take_component_id="take_profile_switch",
    )
    from research.strategies.ema_pullback.execution.managed_bar_open_candidates import (
        collect_managed_bar_open_candidates,
    )

    candidates = collect_managed_bar_open_candidates(
        inherited,
        bar_idx=1,
        direction="long",
        open_=101.0,
        high=101.5,
        low=99.0,
        close=100.5,
    )
    assert any(item.candidate_type == "managed_stop" for item in candidates)


def test_disable_fixed_tp_alias_normalizes_to_disable_initial_tp() -> None:
    assert normalize_take_profile_action("disable_fixed_tp") == "disable_initial_tp"
    fixture = (
        Path(__file__).resolve().parents[1]
        / "research"
        / "experiments"
        / "configs"
        / "fixtures"
        / "smoke_managed_parsing_v2.json"
    )
    loaded = load_strategy_config(__import__("json").loads(fixture.read_text(encoding="utf-8")))
    action = loaded.specs[0].trade_management.exit_management.take_management[0].params.action
    assert action == "disable_initial_tp"


def test_provider_modules_do_not_import_htf_context() -> None:
    provider_dir = (
        Path(__file__).resolve().parents[1]
        / "research"
        / "strategies"
        / "ema_pullback"
        / "execution"
    )
    modules = [
        provider_dir / "managed_exit_provider.py",
        provider_dir / "managed_bar_open_candidates.py",
    ]
    forbidden = (
        "context.pipeline",
        "context_bundle",
        "profile_switch",
        "htf_context",
    )
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for token in forbidden:
                        assert token not in alias.name, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for token in forbidden:
                    assert token not in node.module, f"{path.name} imports from {node.module}"


def test_exit_executed_emitted_on_managed_close() -> None:
    spec = _managed_be_spec()
    n = 4
    close = _series([100.0, 101.0, 99.0, 100.0])
    open_ = _series([100.0, 101.0, 99.5, 100.0])
    high = _series([101.0, 102.0, 100.0, 101.0])
    low = _series([99.5, 101.5, 98.5, 99.5])
    entries = pd.Series([True, False, False, False], index=close.index, dtype=bool)
    provider = ManagedExitProvider(
        phase_rules=spec.trade_management.exit_management.phase_rules,
        stop_management=spec.trade_management.exit_management.stop_management,
        take_management=(),
        runtime_exits=(),
    )
    result = run_managed_execution_loop(
        spec=spec,
        close=close,
        open_=open_,
        high=high,
        low=low,
        entries=entries,
        short_entries=_false_series(n, close.index),
        exit_outputs=_minimal_exit_outputs(n),
        provider=provider,
    )
    types = [event.event_type for event in result.events]
    assert "exit_rule_triggered" in types
    assert "exit_executed" in types
