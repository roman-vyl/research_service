from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("pandas")

import pandas as pd

from research.strategies.ema_pullback.execution.signal_trace import (
    build_signal_trace_from_spec,
    slice_signal_trace,
)
from research.strategies.ema_pullback.execution.exits import PortfolioExitOutputs
from research.strategies.ema_pullback.execution.signals import build_signals_from_spec
from research.strategies.ema_pullback.features.calculations import add_feature_columns_from_plan
from research.strategies.ema_pullback.features.plan import build_feature_plan_from_strategy_spec
from research.strategies.ema_pullback.component_builders import trigger_strong_reclaim_anchor
from research.strategies.ema_pullback.spec import (
    ReclaimTriggerSpec,
    StrongReclaimTriggerSpec,
    strategy_spec_to_dict,
)
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
from research.strategies.ema_pullback.spec_report import strategy_spec_from_report_dict


def _ohlcv(periods: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="h", tz="UTC")
    close = pd.Series(range(100, 100 + periods), index=idx, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )


def test_signal_entry_trace_matches_build_signals_from_spec() -> None:
    spec = make_ema_pullback_strategy_spec()
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(), plan)

    signals = build_signals_from_spec(df, spec, plan)
    trace = build_signal_trace_from_spec(df, spec, plan)

    assert trace.long.signal_entry == signals.entries.fillna(False).astype(bool).tolist()
    assert trace.short.signal_entry == signals.short_entries.fillna(False).astype(bool).tolist()
    assert len(trace.times) == len(df)


def test_build_signals_from_spec_works_with_strong_reclaim_anchor() -> None:
    spec = make_ema_pullback_strategy_spec()
    spec = replace(
        spec,
        components=replace(
            spec.components, trigger=trigger_strong_reclaim_anchor(lookback=2)
        ),
    )
    assert isinstance(spec.components.trigger, StrongReclaimTriggerSpec)
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    signals = build_signals_from_spec(df, spec, plan)
    assert len(signals.entries) == len(df)
    assert len(signals.short_entries) == len(df)


def test_signal_trace_meta_and_internals_for_strong_reclaim_anchor() -> None:
    spec = make_ema_pullback_strategy_spec()
    spec = replace(
        spec,
        components=replace(
            spec.components, trigger=trigger_strong_reclaim_anchor(lookback=2)
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, spec, plan)
    assert trace.meta["trigger_params"] == {"lookback": 2}
    trigger_internals = trace.long.internals["trigger"]
    for key in ("probed", "had_prior_probe", "reclaimed", "trigger"):
        assert key in trigger_internals


def test_signal_trace_meta_includes_trigger_params_for_reclaim() -> None:
    spec = make_ema_pullback_strategy_spec(trigger_lookback=2)
    assert isinstance(spec.components.trigger, ReclaimTriggerSpec)
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, spec, plan)
    assert trace.meta["trigger_params"] == {"lookback": 2}


def test_strategy_spec_roundtrip_from_report_dict() -> None:
    spec = make_ema_pullback_strategy_spec(variant="roundtrip_test", trigger_lookback=3)
    restored = strategy_spec_from_report_dict(strategy_spec_to_dict(spec))
    assert restored.variant == spec.variant
    assert restored.setups[0].component_id == spec.setups[0].component_id
    assert restored.components.trigger.component_id == spec.components.trigger.component_id
    assert isinstance(restored.components.trigger, ReclaimTriggerSpec)
    assert restored.components.trigger.lookback == 3
    assert len(restored.components.blockers) == len(spec.components.blockers)


def test_strategy_spec_roundtrip_preserves_ema_bounce_counter_nested_params() -> None:
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        ema_bounce_counter_setup_spec,
        setup_rule,
    )
    from research.strategies.ema_pullback.spec import EmaBounceCounterSetupSpec

    params = ema_bounce_counter_setup_spec(
        max_bounces=7,
        touch_lookback_bars=13,
    )
    spec = replace(
        make_ema_pullback_strategy_spec(
            fast_period=60,
            anchor_period=200,
            slow_period=600,
        ),
        setups=(
            setup_rule(
                instance_id="bc",
                component_id="ema_bounce_counter_setup",
                params=params,
            ),
        ),
    )
    wire = strategy_spec_to_dict(spec)
    setup_wire = wire["setups"][0]
    assert setup_wire["params"]["max_bounces"] == 7
    assert setup_wire["params"]["touch_lookback_bars"] == 13

    restored = strategy_spec_from_report_dict(wire)
    assert len(restored.setups) == 1
    restored_params = restored.setups[0].params
    assert isinstance(restored_params, EmaBounceCounterSetupSpec)
    assert restored.setups[0].params.max_bounces == 7
    assert restored.anchor_stack.fast.period == 60
    assert restored.anchor_stack.anchor.period == 200
    assert restored.anchor_stack.slow.period == 600
    assert restored_params.max_bounces == 7
    assert restored_params.touch_lookback_bars == 13


def test_strategy_spec_roundtrip_preserves_blocker_htf_regime_gate_params() -> None:
    from dataclasses import asdict
    from tests.ema_pullback_context_helpers import (
        blocker_htf_regime_gate,
        htf_strategy_contexts,
    )

    base = make_ema_pullback_strategy_spec(contexts=htf_strategy_contexts(context_ref="htf_1"))
    spec = replace(
        base,
        components=replace(
            base.components,
            blockers=(blocker_htf_regime_gate(context_ref="htf_1", allowed_regimes=("aligned", "neutral")),),
        ),
    )
    wire = strategy_spec_to_dict(spec)
    blocker = wire["components"]["blockers"][0]
    assert blocker["context_consumption"]["policy"]["params"] == {
        "allowed_regimes": ["aligned", "neutral"],
    }
    restored = strategy_spec_from_report_dict(wire)
    consumption = restored.components.blockers[0].context_consumption
    assert consumption is not None
    assert dict(consumption.policy.params) == {"allowed_regimes": ["aligned", "neutral"]}

    legacy_wire = asdict(spec)
    restored_legacy = strategy_spec_from_report_dict(legacy_wire)
    legacy_consumption = restored_legacy.components.blockers[0].context_consumption
    assert legacy_consumption is not None
    assert dict(legacy_consumption.policy.params) == {"allowed_regimes": ["aligned", "neutral"]}


def test_strategy_spec_roundtrip_preserves_trend_strength_blocker_params() -> None:
    from dataclasses import asdict, replace

    from research.strategies.ema_pullback.component_builders import (
        blocker_trend_strength_episode,
    )
    from research.strategies.ema_pullback.spec import strategy_spec_to_dict

    base = make_ema_pullback_strategy_spec()
    spec = replace(
        base,
        components=replace(
            base.components,
            blockers=(
                blocker_trend_strength_episode(
                    instance_id="ts1",
                    min_adx_peak=27.5,
                    peak_lookback_bars=55,
                ),
            ),
        ),
    )
    wire = strategy_spec_to_dict(spec)
    ts_wire = wire["components"]["blockers"][0]["trend_strength"]
    assert ts_wire["min_adx_peak"] == 27.5
    assert ts_wire["peak_lookback_bars"] == 55

    restored = strategy_spec_from_report_dict(wire)
    params = restored.components.blockers[0].trend_strength
    assert params is not None
    assert params.min_adx_peak == 27.5
    assert params.peak_lookback_bars == 55

    restored_legacy = strategy_spec_from_report_dict(asdict(spec))
    legacy_params = restored_legacy.components.blockers[0].trend_strength
    assert legacy_params is not None
    assert legacy_params.min_adx_peak == 27.5


def test_strategy_spec_roundtrip_preserves_setup_context_consumption() -> None:
    from dataclasses import asdict

    from research.strategies.ema_pullback.component_builders import (
        context_consumption,
        setup_rule,
        untouched_anchor_setup_spec,
    )
    from tests.ema_pullback_context_helpers import htf_strategy_contexts

    base = make_ema_pullback_strategy_spec(contexts=htf_strategy_contexts(context_ref="htf"))
    spec = replace(
        base,
        setups=(
            setup_rule(
                instance_id="setup_ctx",
                component_id="untouched_anchor_setup",
                params=untouched_anchor_setup_spec(lookback=50, active_bars=3),
                context_consumption=context_consumption(
                    context_ref="htf",
                    policy_id="htf_regime_gate",
                    params=(("allowed_regimes", ["aligned"]),),
                ),
            ),
        ),
    )
    wire = strategy_spec_to_dict(spec)
    setup_wire = wire["setups"][0]
    assert setup_wire["context_consumption"]["context_ref"] == "htf"
    assert setup_wire["context_consumption"]["policy"]["policy_id"] == "htf_regime_gate"

    restored = strategy_spec_from_report_dict(wire)
    restored_consumption = restored.setups[0].context_consumption
    assert restored_consumption is not None
    assert restored_consumption.context_ref == "htf"
    assert restored_consumption.policy.policy_id == "htf_regime_gate"
    assert dict(restored_consumption.policy.params) == {"allowed_regimes": ["aligned"]}

    legacy_wire = asdict(spec)
    restored_legacy = strategy_spec_from_report_dict(legacy_wire)
    legacy_consumption = restored_legacy.setups[0].context_consumption
    assert legacy_consumption is not None
    assert legacy_consumption.context_ref == "htf"
    assert legacy_consumption.policy.policy_id == "htf_regime_gate"
    assert dict(legacy_consumption.policy.params) == {"allowed_regimes": ["aligned"]}


def test_signal_trace_after_setup_context_report_roundtrip() -> None:
    from research.strategies.ema_pullback.component_builders import (
        context_consumption,
        setup_rule,
        untouched_anchor_setup_spec,
    )
    from tests.ema_pullback_context_helpers import htf_strategy_contexts

    base = make_ema_pullback_strategy_spec(contexts=htf_strategy_contexts(context_ref="htf"))
    spec = replace(
        base,
        setups=(
            setup_rule(
                instance_id="setup_ctx",
                component_id="untouched_anchor_setup",
                params=untouched_anchor_setup_spec(lookback=50, active_bars=3),
                context_consumption=context_consumption(
                    context_ref="htf",
                    policy_id="htf_regime_gate",
                    params=(("allowed_regimes", ["aligned"]),),
                ),
            ),
        ),
    )

    restored = strategy_spec_from_report_dict(strategy_spec_to_dict(spec))
    assert restored.setups[0].context_consumption is not None
    plan = build_feature_plan_from_strategy_spec(restored)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, restored, plan, context_overlay_ref="htf")
    setup_records = [r for r in trace.context_consumption_trace if r.get("role") == "setup"]
    assert any(r.get("instance_id") == "setup_ctx" for r in setup_records)


def test_signal_trace_after_htf_regime_gate_report_roundtrip() -> None:
    from tests.ema_pullback_context_helpers import (
        blocker_htf_regime_gate,
        htf_strategy_contexts,
    )

    base = make_ema_pullback_strategy_spec(contexts=htf_strategy_contexts(context_ref="htf_1"))
    spec = replace(
        base,
        components=replace(
            base.components,
            blockers=(blocker_htf_regime_gate(context_ref="htf_1", allowed_regimes=("aligned", "neutral")),),
        ),
    )
    restored = strategy_spec_from_report_dict(strategy_spec_to_dict(spec))
    plan = build_feature_plan_from_strategy_spec(restored)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, restored, plan, context_overlay_ref="htf_1")
    assert len(trace.times) == len(df)
    assert any(record.get("policy_id") == "htf_regime_gate" for record in trace.context_consumption_trace)


def test_strategy_spec_roundtrip_preserves_named_contexts() -> None:
    from research.strategies.ema_pullback.component_builders import exit_rsi, trade_management
    from tests.ema_pullback_context_helpers import exit_policy_htf_consumption, htf_strategy_contexts

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(context_ref="htf_1"),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                context_ref="htf_1",
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    wire = strategy_spec_to_dict(spec)
    assert isinstance(wire["contexts"], dict)
    assert "htf_1" in wire["contexts"]
    restored = strategy_spec_from_report_dict(wire)
    assert "htf_1" in restored.contexts_by_ref()
    consumption = restored.trade_management.exit_policy.context_consumption
    assert consumption is not None
    assert consumption.context_ref == "htf_1"


def test_strategy_spec_from_report_dict_accepts_legacy_contexts_list() -> None:
    from dataclasses import asdict
    from research.strategies.ema_pullback.component_builders import exit_rsi, trade_management
    from tests.ema_pullback_context_helpers import exit_policy_htf_consumption, htf_strategy_contexts

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(context_ref="htf_1"),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                context_ref="htf_1",
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    legacy_wire = asdict(spec)
    restored = strategy_spec_from_report_dict(legacy_wire)
    assert "htf_1" in restored.contexts_by_ref()


def test_signal_trace_after_strategy_spec_report_roundtrip() -> None:
    spec = make_ema_pullback_strategy_spec(trigger_lookback=2)
    restored = strategy_spec_from_report_dict(strategy_spec_to_dict(spec))
    plan = build_feature_plan_from_strategy_spec(restored)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, restored, plan)
    assert trace.meta["trigger_params"] == {"lookback": 2}
    assert len(trace.times) == len(df)


def test_strategy_spec_report_roundtrip_accepts_null_optional_atr_ref() -> None:
    """asdict serializes optional ManagementAtrRefSpec as null; report reload must accept it."""
    wire = strategy_spec_to_dict(make_ema_pullback_strategy_spec())
    exit_management = wire["trade_management"]["exit_management"]
    exit_management["mode"] = "managed"
    exit_management["stop_management"] = [
        {
            "rule_id": "be_at_protected",
            "component_id": "break_even_stop",
            "activate_when": {"phase_at_least": "protected"},
            "params": {
                "buffer_type": "none",
                "buffer": 0.0,
                "buffer_atr": 0.0,
                "atr_period": 14,
                "atr": None,
            },
        }
    ]
    restored = strategy_spec_from_report_dict(wire)
    assert restored.trade_management.exit_management.stop_management[0].params.atr is None


def test_portfolio_entry_false_when_stop_not_ready() -> None:
    spec = make_ema_pullback_strategy_spec()
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=30), plan)
    trace = build_signal_trace_from_spec(df, spec, plan)

    for i, (signal, stop_ok, portfolio) in enumerate(
        zip(trace.long.signal_entry, trace.long.stop_ready, trace.long.portfolio_entry, strict=True)
    ):
        assert portfolio == (signal and stop_ok), f"bar {i}"


def test_signal_trace_max_bars_supports_render_window_size() -> None:
    """BFF window endpoint limit aligns with 50k chart render window."""
    from research_api.services.signal_trace_service import MAX_SIGNAL_TRACE_BARS

    assert MAX_SIGNAL_TRACE_BARS >= 50_000

    spec = make_ema_pullback_strategy_spec()
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=6000), plan)
    full = build_signal_trace_from_spec(df, spec, plan)
    sliced = slice_signal_trace(
        full,
        from_time_sec=full.times[0],
        to_time_sec=full.times[-1],
        max_bars=MAX_SIGNAL_TRACE_BARS,
    )
    assert len(sliced.times) > 5000
    assert len(sliced.times) == len(full.times)


def test_slice_signal_trace_respects_window() -> None:
    spec = make_ema_pullback_strategy_spec()
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=40), plan)
    full = build_signal_trace_from_spec(df, spec, plan)
    sliced = slice_signal_trace(
        full,
        from_time_sec=full.times[10],
        to_time_sec=full.times[20],
        max_bars=5000,
    )
    assert len(sliced.times) == 11
    assert sliced.long.direction_ok == full.long.direction_ok[10:21]


def test_slice_signal_trace_empty_htf_with_consumption_trace() -> None:
    """Chart loads trace before overlay ref: htf_context empty, consumption trace full-length."""
    from research.strategies.ema_pullback.component_builders import (
        component_stack,
        direction_ema_anchor_stack,
        exit_rsi,
        risk_no_filter,
        setup_untouched_anchor,
        trade_management,
        trigger_reclaim_anchor,
    )
    from tests.ema_pullback_context_helpers import (
        blocker_htf_regime_gate,
        exit_policy_htf_consumption,
        htf_strategy_contexts,
    )

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(context_ref="htf_1"),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_htf_regime_gate(context_ref="htf_1"),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                context_ref="htf_1",
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=40), plan)
    full = build_signal_trace_from_spec(df, spec, plan, context_overlay_ref=None)
    assert full.htf_context["state"] == []
    assert len(full.context_consumption_trace) >= 1

    sliced = slice_signal_trace(
        full,
        from_time_sec=full.times[10],
        to_time_sec=full.times[20],
        max_bars=5000,
    )
    assert len(sliced.times) == 11
    assert sliced.htf_context["state"] == []
    blocker = next(r for r in sliced.context_consumption_trace if r["role"] == "blockers")
    assert len(blocker["context_applied"]) == 11


def test_slice_signal_trace_with_htf_overlay() -> None:
    from research.strategies.ema_pullback.component_builders import exit_rsi, trade_management
    from tests.ema_pullback_context_helpers import exit_policy_htf_consumption, htf_strategy_contexts

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(context_ref="htf_1"),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                context_ref="htf_1",
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=40), plan)
    full = build_signal_trace_from_spec(df, spec, plan, context_overlay_ref="htf_1")
    assert len(full.htf_context["state"]) == len(full.times)

    sliced = slice_signal_trace(
        full,
        from_time_sec=full.times[5],
        to_time_sec=full.times[15],
        max_bars=5000,
    )
    assert len(sliced.htf_context["state"]) == len(sliced.times) == 11
    assert sliced.htf_context["state"] == full.htf_context["state"][5:16]


def test_signal_trace_uses_side_specific_stop_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = make_ema_pullback_strategy_spec(enabled_sides=("long", "short"))
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=12), plan)

    def fake_exits(
        df_local: pd.DataFrame,
        _spec: object,
        _plan: object,
        *,
        context_bundle: object | None = None,
    ) -> PortfolioExitOutputs:
        _ = context_bundle
        idx = df_local.index
        false_s = pd.Series(False, index=idx, dtype=bool)
        nan_s = pd.Series(float("nan"), index=idx, dtype=float)
        return PortfolioExitOutputs(
            exits=false_s,
            short_exits=false_s,
            sl_stop=nan_s,
            tp_stop=nan_s,
            stop_ready_long=pd.Series([True] * len(idx), index=idx, dtype=bool),
            stop_ready_short=pd.Series([False] * len(idx), index=idx, dtype=bool),
            context_state=pd.Series("neutral", index=idx, dtype="object"),
            profile_long=pd.Series("neutral", index=idx, dtype="object"),
            profile_short=pd.Series("neutral", index=idx, dtype="object"),
            long_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            short_exits_by_profile={"aligned": false_s, "countertrend": false_s, "neutral": false_s},
            sl_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
            tp_stop_by_profile={"aligned": nan_s, "countertrend": nan_s, "neutral": nan_s},
        )

    monkeypatch.setattr(
        "research.strategies.ema_pullback.execution.signal_trace.build_exit_outputs_from_spec",
        fake_exits,
    )

    trace = build_signal_trace_from_spec(df, spec, plan)
    assert all(trace.long.stop_ready)
    assert not any(trace.short.stop_ready)


def _ohlcv_5m(*, periods: int = 12, start: str = "2024-01-01 10:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq="5min", tz="UTC")
    close = pd.Series(100.0, index=idx, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )


def test_component_events_empty_without_emitters() -> None:
    spec = make_ema_pullback_strategy_spec()
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(), plan)
    trace = build_signal_trace_from_spec(df, spec, plan)
    assert trace.component_events == []


def test_ema_bounce_counter_setup_trace_and_events() -> None:
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        component_stack,
        direction_ema_anchor_stack,
        ema_bounce_counter_setup_spec,
        risk_no_filter,
        setup_rule,
        trigger_reclaim_anchor,
    )

    base = make_ema_pullback_strategy_spec(
        enabled_sides=("long",),
        fast_period=50,
        anchor_period=200,
        slow_period=500,
    )
    spec = replace(
        base,
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
        setups=(
            setup_rule(
                instance_id="bounce_counter",
                component_id="ema_bounce_counter_setup",
                params=ema_bounce_counter_setup_spec(
                    max_bounces=3,
                    touch_lookback_bars=3,
                ),
            ),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    df = add_feature_columns_from_plan(_ohlcv(periods=8), plan)
    df["close"] = 105.0
    df["high"] = 106.0
    df["low"] = [104.0, 99.0, 104.0, 99.0, 99.0, 104.0, 104.0, 104.0]
    bounce_cols = plan.setup_columns_for("bounce_counter")
    df[bounce_cols["fast"]] = 110.0
    df[bounce_cols["anchor"]] = 100.0
    df[bounce_cols["slow"]] = 90.0

    trace = build_signal_trace_from_spec(df, spec, plan)

    setup_internals = trace.long.internals["setups"]["bounce_counter"]
    assert setup_internals["pending_bounce_start"] == [
        False,
        True,
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert setup_internals["pending_bounce_end"][3] is True
    assert setup_internals["completed_bounce_count"] == [0, 0, 0, 0, 1, 1, 1, 2]
    assert trace.long.signal_entry == build_signals_from_spec(df, spec, plan).entries.tolist()

    setup_events = [event for event in trace.component_events if event.role == "setup"]
    bounce_events = [
        event
        for event in setup_events
        if event.metadata.get("event_name") in {
            "bounce_opportunity_start",
            "pending_bounce_start",
            "pending_bounce_end",
        }
    ]
    assert len(bounce_events) == 6
    first = [event for event in bounce_events if event.span_id == bounce_events[0].span_id]
    by_type = {event.event_type: event for event in first}
    assert by_type["source"].time == trace.times[1]
    assert by_type["span_start"].time == trace.times[1]
    assert by_type["span_end"].time == trace.times[3]
    assert by_type["source"].feature_family == "ema"
    assert by_type["source"].component_id == "ema_bounce_counter_setup"
    required_bounce_metadata = {
        "event_name",
        "trend_active",
        "trend_episode_id",
        "armed",
        "raw_touch",
        "pending_bounce",
        "in_touch_lookback",
        "setup_allowed",
        "touch_lookback_bars",
        "touch_lookback_left",
        "completed_bounce_count",
        "effective_bounce_number",
        "max_bounces",
        "price_side_of_anchor",
        "fast_ema",
        "anchor_ema",
        "slow_ema",
    }
    for event in bounce_events:
        assert required_bounce_metadata.issubset(event.metadata.keys())
    source_meta = by_type["source"].metadata
    assert source_meta["raw_touch"] is setup_internals["raw_touch"][1]
    assert source_meta["trend_active"] is setup_internals["trend_active"][1]
    assert source_meta["in_touch_lookback"] is setup_internals["in_touch_lookback"][1]
    span_end_meta = by_type["span_end"].metadata
    assert span_end_meta["in_touch_lookback"] is setup_internals["in_touch_lookback"][3]
    assert span_end_meta["raw_touch"] is setup_internals["raw_touch"][3]
    trend_events = [
        event
        for event in setup_events
        if event.metadata.get("event_name") in {"trend_start", "trend_break"}
    ]
    for event in trend_events:
        assert required_bounce_metadata.issubset(event.metadata.keys())
        assert event.metadata["event_name"] in {"trend_start", "trend_break"}
    # Metadata enrichment must not change trading outputs.
    from research.strategies.ema_pullback.components.setup import ema_bounce_counter_setup_trace

    direct_trace = ema_bounce_counter_setup_trace(
        df,
        bounce_cols["fast"],
        bounce_cols["anchor"],
        bounce_cols["slow"],
        max_bounces=3,
        touch_lookback_bars=3,
        side="long",
    )
    assert list(setup_internals["setup_allowed"]) == direct_trace["setup_allowed"].tolist()
    # The raw touch at index 3 is the final active lookback bar; it closes the
    # first span but does not emit another source/span_start.
    assert [
        event.time
        for event in bounce_events
        if event.event_type in {"source", "span_start"}
    ].count(trace.times[3]) == 0


def test_rising_edge_indices_synthetic_source() -> None:
    from research.strategies.ema_pullback.execution.signal_trace import _rising_edge_indices

    raw = [False, True, True, True, False, False, True, True]
    assert _rising_edge_indices(raw) == [1, 6]


def test_contiguous_blocked_runs_span_end_on_last_blocked_bar() -> None:
    from research.strategies.ema_pullback.execution.signal_trace import _contiguous_blocked_runs

    blocked = [False, True, True, True, True, False, True, True]
    assert _contiguous_blocked_runs(blocked) == [(1, 4), (6, 7)]


def test_component_events_htf_blocker_emits_semantic_span() -> None:
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        blocker_extreme_rsi,
        component_stack,
        direction_ema_anchor_stack,
        setup_untouched_anchor,
        trigger_reclaim_anchor,
    )

    base = make_ema_pullback_strategy_spec(base_timeframe="5m")
    spec = replace(
        base,
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(
                blocker_extreme_rsi(
                    instance_id="rsi_1h",
                    timeframe="1h",
                    lookback=1,
                    long_block_above=80.0,
                ),
            ),
            trigger=trigger_reclaim_anchor(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    df = _ohlcv_5m(periods=12)
    enriched = add_feature_columns_from_plan(df, plan)
    rsi_col = plan.rsi_columns[("1h", 14)]
    enriched[rsi_col] = 90.0
    trace = build_signal_trace_from_spec(enriched, spec, plan)
    entry_events = [e for e in trace.component_events if e.role == "entry_block"]
    assert len(entry_events) == 3
    by_type = {e.event_type: e for e in entry_events}
    assert set(by_type) == {"source", "span_start", "span_end"}
    assert by_type["span_start"].time == trace.times[0]
    assert by_type["span_end"].time == trace.times[-1]
    assert by_type["span_end"].time != trace.times[-1] + 300
    assert by_type["source"].source_timeframe == "1h"
    assert by_type["source"].base_timeframe == "5m"
    assert by_type["span_start"].span_id == by_type["span_end"].span_id == by_type["source"].span_id
    assert by_type["source"].metadata.get("rsi_value") is not None


def test_component_events_rsi_exit_point() -> None:
    from research.strategies.ema_pullback.component_builders import exit_policy, exit_rsi, trade_management

    spec = make_ema_pullback_strategy_spec(
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy(
                always_on=(exit_rsi(instance_id="rsi_exit"),),
                aligned=(),
                countertrend=(),
                neutral=(),
            ),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    enriched = add_feature_columns_from_plan(_ohlcv(periods=20), plan)
    rsi_col = plan.rsi_columns[("base", 14)]
    enriched[rsi_col] = 75.0
    trace = build_signal_trace_from_spec(enriched, spec, plan)
    exit_events = [e for e in trace.component_events if e.role == "exit_signal"]
    assert len(exit_events) == len(trace.times)
    sample = exit_events[0]
    assert sample.component_id == "rsi_signal_exit"
    assert sample.event_type == "point"
    assert sample.metadata.get("condition") == "exit_above"
    assert sample.label == "Exit↓"


def test_component_events_counter_candle_only_is_empty() -> None:
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        blocker_counter_candle,
        component_stack,
        direction_ema_anchor_stack,
        setup_untouched_anchor,
        trigger_reclaim_anchor,
    )

    base = make_ema_pullback_strategy_spec()
    spec = replace(
        base,
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_counter_candle(),),
            trigger=trigger_reclaim_anchor(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    enriched = add_feature_columns_from_plan(_ohlcv(periods=20), plan)
    trace = build_signal_trace_from_spec(enriched, spec, plan)
    assert trace.component_events == []


def test_slice_signal_trace_partial_span_may_show_span_end_only() -> None:
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        blocker_extreme_rsi,
        component_stack,
        direction_ema_anchor_stack,
        setup_untouched_anchor,
        trigger_reclaim_anchor,
    )

    base = make_ema_pullback_strategy_spec(base_timeframe="5m")
    spec = replace(
        base,
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(
                blocker_extreme_rsi(instance_id="rsi1", timeframe="1h", lookback=1),
            ),
            trigger=trigger_reclaim_anchor(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    enriched = add_feature_columns_from_plan(_ohlcv_5m(periods=12), plan)
    rsi_col = plan.rsi_columns[("1h", 14)]
    enriched[rsi_col] = 90.0
    full = build_signal_trace_from_spec(enriched, spec, plan)
    assert len(full.component_events) == 3
    sliced = slice_signal_trace(
        full,
        from_time_sec=full.times[6],
        to_time_sec=full.times[-1],
    )
    types = {e.event_type for e in sliced.component_events}
    assert "span_end" in types
    assert "span_start" not in types
