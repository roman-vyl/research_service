"""Slice 4.5: legacy path removal and single managed runtime guards."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from research.strategies.ema_pullback.execution import backtest
from research.strategies.ema_pullback.execution.managed_execution_loop import (
    run_managed_execution_loop,
)
from research.strategies.ema_pullback.execution.managed_exit_provider import ManagedExitProvider

from tests.test_managed_execution_integration import (
    _managed_be_spec,
    _managed_empty_spec,
    _minimal_exit_outputs,
    _series,
    _false_series,
)


_EMA_PULLBACK_ROOT = Path(__file__).resolve().parents[1] / "research" / "strategies" / "ema_pullback"

_PRODUCTION_SCAN_PATHS = (
    _EMA_PULLBACK_ROOT / "execution" / "backtest.py",
    _EMA_PULLBACK_ROOT / "execution" / "signal_trace.py",
    _EMA_PULLBACK_ROOT / "execution" / "results.py",
    _EMA_PULLBACK_ROOT / "execution" / "managed_execution_loop.py",
    _EMA_PULLBACK_ROOT / "instance_loader.py",
    _EMA_PULLBACK_ROOT / "component_builders.py",
    _EMA_PULLBACK_ROOT / "components" / "registry.py",
)


def test_no_run_managed_bar_loop_in_production_modules() -> None:
    for path in _PRODUCTION_SCAN_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "run_managed_bar_loop" not in text, f"{path} still references run_managed_bar_loop"


def test_no_execution_combiner_or_adapter_modules() -> None:
    execution_dir = _EMA_PULLBACK_ROOT / "execution"
    names = {path.name for path in execution_dir.glob("*.py")}
    assert "execution_combiner.py" not in names
    assert "execution_adapters.py" not in names


def test_legacy_authoring_builders_removed_from_component_builders() -> None:
    import research.strategies.ema_pullback.component_builders as builders

    assert not hasattr(builders, "break_even_stop_rule")
    assert not hasattr(builders, "exit_management")
    assert not hasattr(builders, "exit_management_group")
    assert not hasattr(builders, "exit_management_profiles")


def test_registry_has_no_exit_management_role() -> None:
    from research.strategies.ema_pullback.components.registry import COMPONENT_REGISTRY

    assert "exit_management" not in COMPONENT_REGISTRY


@pytest.mark.optional_vectorbt
def test_managed_with_rules_routes_to_v2_execution_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("vectorbt")
    calls: list[int] = []
    original = backtest.run_managed_execution_loop

    def _spy(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(backtest, "run_managed_execution_loop", _spy)

    spec = _managed_be_spec()
    n = 6
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series([100.0, 101.0, 102.0, 101.0, 100.0, 100.5], index=idx, dtype=float)
    data = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0,
        }
    )
    backtest.run_strategy_spec(spec, data)
    assert calls == [1]


def test_entry_bar_skips_provider_end_of_bar_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_bars: list[int] = []
    original = ManagedExitProvider.update_end_of_bar_snapshot

    def _spy(self: ManagedExitProvider, *args: object, **kwargs: object) -> object:
        bar_idx = kwargs.get("bar_idx")
        if bar_idx is None and len(args) >= 3:
            bar_idx = args[2]
        assert isinstance(bar_idx, int)
        update_bars.append(bar_idx)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ManagedExitProvider, "update_end_of_bar_snapshot", _spy)

    spec = _managed_empty_spec()
    n = 4
    close = _series([100.0, 101.0, 102.0, 103.0])
    open_ = close - 0.1
    high = close + 0.5
    low = close - 0.5
    entries = pd.Series([True, False, False, False], index=close.index, dtype=bool)
    short_entries = _false_series(n, close.index)
    exit_management = spec.trade_management.exit_management
    provider = ManagedExitProvider(
        phase_rules=exit_management.phase_rules,
        stop_management=(),
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
        short_entries=short_entries,
        exit_outputs=_minimal_exit_outputs(n),
        provider=provider,
    )
    assert 0 not in update_bars
    assert update_bars == [1, 2, 3]
