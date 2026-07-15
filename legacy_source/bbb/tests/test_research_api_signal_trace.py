"""Signal trace endpoint tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from research_api.contracts.signal_trace import SignalTraceBundle
from research_api.main import app
from research_api.services.signal_trace_service import _cached_full_trace_key, _warmup_bars_ms
from research.strategies.ema_pullback.component_builders import trade_management
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
from tests.ema_pullback_context_helpers import exit_policy_htf_consumption, htf_strategy_contexts


def test_signal_trace_endpoint_returns_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = SignalTraceBundle(
        times=[1, 2],
        meta={
            "variant": "v1",
            "component_ids": {
                "direction": "ema_anchor_stack_trend",
                "setups": [
                    {
                        "instance_id": "setup",
                        "component_id": "untouched_anchor_setup",
                    }
                ],
                "trigger": "reclaim_anchor",
                "risk": "no_risk_filter",
            },
            "setup_params": [
                {
                    "instance_id": "setup",
                    "component_id": "untouched_anchor_setup",
                    "lookback": 50,
                    "active_bars": 3,
                }
            ],
            "blocker_instances": [{"instance_id": "no_blockers", "component_id": "no_blockers"}],
        },
        long={
            "direction_ok": [True, False],
            "blockers_ok": [True, True],
            "setup_ok": [False, True],
            "trigger_ok": [True, True],
            "risk_ok": [True, True],
            "signal_entry": [False, False],
            "stop_ready": [True, True],
            "portfolio_entry": [False, False],
            "internals": {},
        },
        short={
            "direction_ok": [False, False],
            "blockers_ok": [True, True],
            "setup_ok": [False, False],
            "trigger_ok": [False, False],
            "risk_ok": [True, True],
            "signal_entry": [False, False],
            "stop_ready": [True, True],
            "portfolio_entry": [False, False],
            "internals": {},
        },
        component_events=[
            {
                "time": 1,
                "event_type": "span_start",
                "role": "entry_block",
                "side": "long",
                "component_id": "rsi_lookback_extreme_blocker",
                "instance_id": "rsi1",
                "label": "Block▶",
                "tooltip": None,
                "span_id": "rsi1:long:1",
                "feature_family": "rsi",
                "source_timeframe": "1h",
                "base_timeframe": "5m",
                "metadata": {"rsi_value": 85.0, "condition": "block_start", "threshold": 80.0},
            }
        ],
    )

    def _fake_fetch(**_: object) -> SignalTraceBundle:
        return sample

    monkeypatch.setattr(
        "research_api.routers.research_runs.fetch_signal_trace_bundle",
        _fake_fetch,
    )

    client = TestClient(app)
    res = client.get(
        "/api/research/runs/run1/signal-trace",
        params={"variant": "v1", "from": 0, "to": 1000},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["times"] == [1, 2]
    assert body["long"]["setup_ok"] == [False, True]
    assert body["component_events"][0]["role"] == "entry_block"
    assert body["component_events"][0]["event_type"] == "span_start"
    assert body["component_events"][0]["feature_family"] == "rsi"
    assert body["component_events"][0]["metadata"]["threshold"] == 80.0


def test_context_consumption_trace_record_accepts_setup_instance_id() -> None:
    bundle = SignalTraceBundle(
        times=[1],
        meta={
            "variant": "v1",
            "component_ids": {
                "direction": "ema_anchor_stack_trend",
                "setups": [{"instance_id": "setup_ctx", "component_id": "untouched_anchor_setup"}],
                "trigger": "reclaim_anchor",
                "risk": "no_risk_filter",
            },
            "setup_params": [
                {
                    "instance_id": "setup_ctx",
                    "component_id": "untouched_anchor_setup",
                    "lookback": 50,
                    "active_bars": 3,
                }
            ],
            "blocker_instances": [],
        },
        context_consumption_trace=[
            {
                "role": "setup",
                "component_id": "untouched_anchor_setup",
                "instance_id": "setup_ctx",
                "setup_instance_id": "setup_ctx",
                "context_ref": "htf",
                "policy_id": "htf_regime_gate",
                "context_applied": [False],
                "outcome": {
                    "local_setup_allowed": [True],
                    "context_gate_allowed": [False],
                    "final_setup_allowed": [False],
                },
            }
        ],
        long={
            "direction_ok": [True],
            "blockers_ok": [True],
            "setup_ok": [False],
            "trigger_ok": [True],
            "risk_ok": [True],
            "signal_entry": [False],
            "stop_ready": [True],
            "portfolio_entry": [False],
            "internals": {},
        },
        short={
            "direction_ok": [False],
            "blockers_ok": [True],
            "setup_ok": [False],
            "trigger_ok": [False],
            "risk_ok": [True],
            "signal_entry": [False],
            "stop_ready": [True],
            "portfolio_entry": [False],
            "internals": {},
        },
    )
    assert bundle.context_consumption_trace[0].setup_instance_id == "setup_ctx"


def test_signal_trace_warmup_ignores_htf_without_context_consumption() -> None:
    """always_on-only spec: no strategy.contexts → warmup is anchor/setup only."""
    spec = make_ema_pullback_strategy_spec(
        base_timeframe="5m",
        fast_period=20,
        anchor_period=50,
        slow_period=200,
        setup_lookback=50,
    )
    assert spec.contexts == ()
    warmup_ms = _warmup_bars_ms(spec, "5m")
    htf_slow_warmup_ms = 200 * 4 * 60 * 60 * 1000
    assert warmup_ms < htf_slow_warmup_ms


def test_signal_trace_cache_key_includes_context_overlay_ref() -> None:
    base = _cached_full_trace_key("run", "v1", 1000, 2000)
    with_ref = _cached_full_trace_key("run", "v1", 1000, 2000, "htf_1")
    assert base != with_ref
    assert with_ref.endswith(":htf_1")
    """Target shape: strategy.contexts.htf drives HTF warmup (via feature plan)."""
    from research.strategies.ema_pullback.component_builders import exit_rsi

    spec = make_ema_pullback_strategy_spec(
        base_timeframe="5m",
        fast_period=20,
        anchor_period=50,
        slow_period=200,
        setup_lookback=50,
        contexts=htf_strategy_contexts(
            timeframe="4h",
            fast_period=20,
            anchor_period=50,
            slow_period=200,
        ),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    assert len(spec.contexts) == 1
    warmup_ms = _warmup_bars_ms(spec, "5m")
    assert warmup_ms >= 200 * 4 * 60 * 60 * 1000


def test_signal_trace_meta_validates_dual_setup_stack() -> None:
    """Regression: stack-aware meta from build_signal_trace_from_spec passes SignalTraceMeta."""
    from dataclasses import replace

    import pandas as pd

    from research.strategies.ema_pullback.component_builders import (
        ema_bounce_counter_setup_spec,
        setup_rule,
    )
    from research.strategies.ema_pullback.execution.signal_trace import build_signal_trace_from_spec
    from research.strategies.ema_pullback.features.calculations import add_feature_columns_from_plan
    from research.strategies.ema_pullback.features.plan import build_feature_plan_from_strategy_spec
    from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
    from research_api.services.signal_trace_service import _to_contract

    base = make_ema_pullback_strategy_spec(enabled_sides=("long",))
    spec = replace(
        base,
        setups=(
            setup_rule(
                instance_id="untouched_anchor",
                component_id="untouched_anchor_setup",
                params=base.setups[0].params,
            ),
            setup_rule(
                instance_id="bounce_counter",
                component_id="ema_bounce_counter_setup",
                params=ema_bounce_counter_setup_spec(max_bounces=1),
            ),
        ),
    )
    idx = pd.date_range("2024-01-01", periods=40, freq="h", tz="UTC")
    close = pd.Series(range(100, 140), index=idx, dtype=float)
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    enriched = add_feature_columns_from_plan(df, plan)
    trace_data = build_signal_trace_from_spec(enriched, spec, plan)
    bundle = _to_contract(trace_data)

    setup_instance_ids = {entry.instance_id for entry in bundle.meta.setup_params}
    assert setup_instance_ids == {"untouched_anchor", "bounce_counter"}
    component_setup_ids = {ref.instance_id for ref in bundle.meta.component_ids.setups}
    assert component_setup_ids == {"untouched_anchor", "bounce_counter"}
    assert "untouched_anchor" in trace_data.long.internals["setups"]
    assert "bounce_counter" in trace_data.long.internals["setups"]
    setup_event_ids = {
        event.instance_id
        for event in bundle.component_events
        if event.role == "setup"
    }
    assert "bounce_counter" in setup_event_ids


def test_to_open_time_ms_exclusive_end_returns_full_50k_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """to_open_time_ms uses market-style exclusive end; slice includes first and last bar."""
    from types import SimpleNamespace

    import pandas as pd

    from data_engine.contracts import timeframe_ms
    from research.strategies.ema_pullback.execution.signal_trace import (
        SideSignalTrace,
        SignalTraceBundleData,
    )
    from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
    from research_api.services import signal_trace_service as sts
    from research_api.services.signal_trace_service import MAX_SIGNAL_TRACE_BARS

    n = MAX_SIGNAL_TRACE_BARS
    bar_ms = timeframe_ms("5m")
    bar_sec = bar_ms // 1000
    t_first_sec = 1_700_000_000
    t_last_sec = t_first_sec + (n - 1) * bar_sec
    t_first_ms = t_first_sec * 1000
    t_last_ms = t_last_sec * 1000
    times = [t_first_sec + i * bar_sec for i in range(n)]

    def side(length: int) -> SideSignalTrace:
        false = [False] * length
        true = [True] * length
        return SideSignalTrace(
            direction_ok=false,
            blockers_ok=true,
            setup_ok=false,
            trigger_ok=false,
            risk_ok=true,
            signal_entry=false,
            stop_ready=true,
            portfolio_entry=false,
            internals={},
        )

    full_trace = SignalTraceBundleData(
        times=times,
        meta={
            "variant": "v1",
            "component_ids": {
                "direction": "ema_anchor_stack_trend",
                "setups": [{"instance_id": "setup", "component_id": "untouched_anchor_setup"}],
                "trigger": "reclaim_anchor",
                "risk": "no_risk_filter",
            },
            "setup_params": [],
            "blocker_instances": [],
        },
        htf_context={"state": [], "fast": [], "anchor": [], "slow": [], "meta": {}},
        context_consumption_trace=[],
        component_events=[],
        long=side(n),
        short=side(n),
    )

    spec = make_ema_pullback_strategy_spec()
    report = SimpleNamespace(
        family="ema_pullback",
        symbol="BTCUSDT",
        timeframe="5m",
        variants=[
            SimpleNamespace(
                variant="v1",
                strategy_spec={},
            )
        ],
    )

    one_row = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [1.0],
        },
        index=pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"),
    )

    monkeypatch.setattr(sts, "load_run_report", lambda run_id: report)
    monkeypatch.setattr(sts, "strategy_spec_from_report_dict", lambda _: spec)
    monkeypatch.setattr(sts, "_warmup_bars_ms", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sts, "_load_ohlcv_frame", lambda **kwargs: one_row)
    monkeypatch.setattr(sts, "add_feature_columns_from_plan", lambda df, plan: df)
    monkeypatch.setattr(sts, "build_signal_trace_from_spec", lambda *args, **kwargs: full_trace)
    sts._TRACE_CACHE.clear()

    bundle = sts.fetch_signal_trace_bundle(
        run_id="run1",
        variant_key="v1",
        from_ms=t_first_ms,
        to_open_time_ms=t_last_ms,
    )

    assert len(bundle.times) == n
    assert bundle.times[0] == t_first_sec
    assert bundle.times[-1] == t_last_sec


def test_to_contract_preserves_exit_management_internals() -> None:
    from research.strategies.ema_pullback.execution.signal_trace import (
        SideSignalTrace,
        SignalTraceBundleData,
    )
    from research_api.services.signal_trace_service import _to_contract

    trace = SignalTraceBundleData(
        times=[100, 101],
        meta={
            "variant": "v1",
            "component_ids": {
                "direction": "ema_anchor_stack_trend",
                "setups": [{"instance_id": "setup", "component_id": "untouched_anchor_setup"}],
                "trigger": "reclaim_anchor",
                "risk": "no_risk_filter",
            },
            "setup_params": [],
            "blocker_instances": [],
        },
        htf_context={"state": [], "fast": [], "anchor": [], "slow": [], "meta": {}},
        context_consumption_trace=[],
        long=SideSignalTrace(
            direction_ok=[True, True],
            blockers_ok=[True, True],
            setup_ok=[False, False],
            trigger_ok=[False, False],
            risk_ok=[True, True],
            signal_entry=[False, False],
            stop_ready=[True, True],
            portfolio_entry=[False, False],
            internals={
                "exit_management": {
                    "effective_stop_price": [90.0, 100.0],
                    "pending_stop_price": [100.0, None],
                    "break_even_active": [True, True],
                    "break_even_triggered_on_bar": [True, False],
                    "active_stop_management_source": ["always_on", "always_on"],
                },
            },
        ),
        short=SideSignalTrace(
            direction_ok=[False, False],
            blockers_ok=[True, True],
            setup_ok=[False, False],
            trigger_ok=[False, False],
            risk_ok=[True, True],
            signal_entry=[False, False],
            stop_ready=[True, True],
            portfolio_entry=[False, False],
            internals={},
        ),
        component_events=[],
    )
    bundle = _to_contract(trace)
    em = bundle.long.internals["exit_management"]
    assert em["effective_stop_price"][0] == 90.0
    assert em["pending_stop_price"][0] == 100.0
    assert em["break_even_triggered_on_bar"][0] is True
    assert em["effective_stop_price"][1] == 100.0
