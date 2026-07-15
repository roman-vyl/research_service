"""Phase 4 — context consumption trace and v5 trade attribution."""

from __future__ import annotations

import pytest

from research.strategies.ema_pullback.component_builders import (
    blocker_none,
    component_stack,
    context_consumption,
    direction_ema_anchor_stack,
    risk_no_filter,
    setup_rule,
    untouched_anchor_setup_spec,
    setup_untouched_anchor,
    trigger_reclaim_anchor,
)
from research.strategies.ema_pullback.context.policies import HTF_REGIME_GATE_POLICY
from research.strategies.ema_pullback.execution.results import extract_trade_records
from research.strategies.ema_pullback.execution.signal_trace import build_signal_trace_from_spec
from research.strategies.ema_pullback.features.calculations import add_feature_columns_from_plan
from research.strategies.ema_pullback.features.plan import build_feature_plan_from_strategy_spec
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec
from tests.ema_pullback_context_helpers import (
    blocker_htf_regime_gate,
    context_bundle_for_spec,
    exit_policy_htf_consumption,
    htf_strategy_contexts,
)


def test_signal_trace_emits_context_consumption_trace() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    from research.strategies.ema_pullback.component_builders import exit_rsi, trade_management

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_htf_regime_gate(allowed_regimes=("aligned",)),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
        trade_management_spec=trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                aligned=(exit_rsi(instance_id="rsi_profile"),),
            ),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    close = pd.Series([100.0, 101.0, 102.0], index=idx)
    ohlcv = pd.DataFrame(
        {"close": close, "open": close, "high": close, "low": close, "volume": 1.0},
        index=idx,
    )
    df = add_feature_columns_from_plan(ohlcv, plan)
    cols = plan.htf_context_columns_for("htf")
    df[cols["fast"]] = [103.0, 101.0, 102.0]
    df[cols["anchor"]] = [102.0, 102.0, 102.0]
    df[cols["slow"]] = [101.0, 103.0, 102.0]

    trace = build_signal_trace_from_spec(df, spec, plan, context_overlay_ref="htf")
    roles = {record["role"] for record in trace.context_consumption_trace}
    assert "exit_policy" in roles
    assert "blockers" in roles
    exit_record = next(r for r in trace.context_consumption_trace if r["role"] == "exit_policy")
    assert exit_record["context_ref"] == "htf"
    assert exit_record["policy_id"] == "exit_profile_by_htf_state"
    assert exit_record["context_applied"] == [True, True, True]
    blocker_record = next(
        r
        for r in trace.context_consumption_trace
        if r["role"] == "blockers" and r.get("outcome", {}).get("evaluated_side") == "long"
    )
    assert blocker_record["policy_id"] == "htf_regime_gate"
    assert blocker_record["context_applied"] == [True, False, False]
    assert blocker_record["outcome"]["raw_state"] == ["up", "down", "neutral"]
    assert blocker_record["outcome"]["allowed_regimes"] == ["aligned"]
    assert blocker_record["outcome"]["resolved_regime"] == ["aligned", "countertrend", "neutral"]


def test_signal_trace_emits_setup_context_diagnostics_split_fields() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(),
        setups=(
            setup_rule(
                instance_id="setup_ctx",
                component_id=setup_untouched_anchor(),
                params=untouched_anchor_setup_spec(lookback=1, active_bars=3),
                context_consumption=context_consumption(
                    context_ref="htf",
                    policy_id=HTF_REGIME_GATE_POLICY,
                    params=(("allowed_regimes", ["aligned"]),),
                ),
            ),
        ),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_none(),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    close = pd.Series([100.0, 101.0, 102.0], index=idx)
    ohlcv = pd.DataFrame(
        {"close": close, "open": close, "high": close, "low": close, "volume": 1.0},
        index=idx,
    )
    df = add_feature_columns_from_plan(ohlcv, plan)
    cols = plan.htf_context_columns_for("htf")
    df[cols["fast"]] = [103.0, 101.0, 102.0]
    df[cols["anchor"]] = [102.0, 102.0, 102.0]
    df[cols["slow"]] = [101.0, 103.0, 102.0]

    trace = build_signal_trace_from_spec(df, spec, plan, context_overlay_ref="htf")
    setup_record = next(
        r
        for r in trace.context_consumption_trace
        if r["role"] == "setup"
        and r["instance_id"] == "setup_ctx"
        and r.get("outcome", {}).get("evaluated_side") == "long"
    )
    outcome = setup_record["outcome"]
    assert setup_record["setup_instance_id"] == "setup_ctx"
    assert setup_record["policy_id"] == "htf_regime_gate"
    assert outcome["allowed_regimes"] == ["aligned"]
    assert outcome["raw_state"] == ["up", "down", "neutral"]
    assert outcome["resolved_regime"] == ["aligned", "countertrend", "neutral"]
    assert len(outcome["local_setup_allowed"]) == len(trace.times)
    assert outcome["context_gate_allowed"] == [True, False, False]
    assert len(outcome["final_setup_allowed"]) == len(trace.times)


def test_setup_component_events_persist_when_context_gate_blocks_final_mask() -> None:
    """Local bounce events stay in component_events[] when HTF gate blocks final setup."""
    pytest.importorskip("pandas")
    import pandas as pd
    from dataclasses import replace

    from research.strategies.ema_pullback.component_builders import (
        component_stack,
        context_consumption,
        direction_ema_anchor_stack,
        ema_bounce_counter_setup_spec,
        risk_no_filter,
        setup_rule,
        trigger_reclaim_anchor,
    )

    bounce_setup = setup_rule(
        instance_id="bounce_counter",
        component_id="ema_bounce_counter_setup",
        params=ema_bounce_counter_setup_spec(
            max_bounces=3,
            touch_lookback_bars=3,
        ),
    )
    base = make_ema_pullback_strategy_spec(
        enabled_sides=("long",),
        contexts=htf_strategy_contexts(),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_none(),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
        setups=(bounce_setup,),
    )
    gated_setup = setup_rule(
        instance_id="bounce_counter",
        component_id="ema_bounce_counter_setup",
        params=bounce_setup.params,
        context_consumption=context_consumption(
            context_ref="htf",
            policy_id=HTF_REGIME_GATE_POLICY,
            params=(("allowed_regimes", ["countertrend"]),),
        ),
    )
    spec_local_only = base
    spec_gated = replace(base, setups=(gated_setup,))

    idx = pd.date_range("2024-01-01 10:00", periods=8, freq="5min", tz="UTC")
    close = pd.Series(105.0, index=idx, dtype=float)
    ohlcv = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": [104.0, 99.0, 104.0, 99.0, 99.0, 104.0, 104.0, 104.0],
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )

    def _trace_for(spec):  # type: ignore[no-untyped-def]
        plan = build_feature_plan_from_strategy_spec(spec)
        df = add_feature_columns_from_plan(ohlcv, plan)
        bounce_cols = plan.setup_columns_for("bounce_counter")
        df[bounce_cols["fast"]] = 110.0
        df[bounce_cols["anchor"]] = 100.0
        df[bounce_cols["slow"]] = 90.0
        cols = plan.htf_context_columns_for("htf")
        df[cols["fast"]] = 103.0
        df[cols["anchor"]] = 102.0
        df[cols["slow"]] = 101.0
        return build_signal_trace_from_spec(df, spec, plan, context_overlay_ref="htf")

    trace_local = _trace_for(spec_local_only)
    trace_gated = _trace_for(spec_gated)

    def _bounce_events(trace):  # type: ignore[no-untyped-def]
        return [
            event
            for event in trace.component_events
            if event.role == "setup"
            and event.metadata.get("event_name")
            in {
                "bounce_opportunity_start",
                "pending_bounce_start",
                "pending_bounce_end",
            }
        ]

    local_events = _bounce_events(trace_local)
    gated_events = _bounce_events(trace_gated)
    assert len(local_events) > 0
    assert gated_events == local_events

    setup_record = next(
        r
        for r in trace_gated.context_consumption_trace
        if r["role"] == "setup" and r["instance_id"] == "bounce_counter"
    )
    outcome = setup_record["outcome"]
    assert outcome["evaluated_side"] == "long"
    assert any(outcome["local_setup_allowed"])
    assert not any(outcome["context_gate_allowed"])
    assert not any(outcome["final_setup_allowed"])
    assert all(regime == "aligned" for regime in outcome["resolved_regime"])


def test_trade_records_include_separate_entry_and_exit_consumption() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_htf_regime_gate(allowed_regimes=("aligned",)),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    idx = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    close = pd.Series([100.0], index=idx)
    ohlcv = pd.DataFrame(
        {"close": close, "open": close, "high": close, "low": close, "volume": 1.0},
        index=idx,
    )
    df = add_feature_columns_from_plan(ohlcv, plan)
    cols = plan.htf_context_columns_for("htf")
    df[cols["fast"]] = [103.0]
    df[cols["anchor"]] = [102.0]
    df[cols["slow"]] = [101.0]
    bundle = context_bundle_for_spec(spec, df, plan)
    context_state = bundle.get("htf").state_series()
    profile_long = pd.Series(["aligned"], index=idx)
    profile_short = pd.Series(["neutral"], index=idx)

    records_df = pd.DataFrame(
        [
            {
                "direction": 0,
                "status": 1,
                "entry_idx": 0,
                "exit_idx": 0,
                "entry_price": 100.0,
                "exit_price": 101.0,
                "size": 1.0,
                "pnl": 1.0,
                "return": 0.01,
            }
        ]
    )

    class _Trades:
        records = records_df

    class _Pf:
        trades = _Trades()

    records = extract_trade_records(
        _Pf(),
        close,
        profile_long=profile_long,
        profile_short=profile_short,
        context_state=context_state,
        strategy_spec=spec,
        context_bundle=bundle,
    )
    assert len(records) == 1
    entry_cc = records[0]["entry_context_consumption"]
    assert entry_cc["policy_id"] == "htf_regime_gate"
    assert entry_cc["applied"] is True
    assert "exit_context_consumption" not in records[0]


def test_trade_entry_consumption_uses_last_consuming_blocker_in_spec_order() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    from research.strategies.ema_pullback.component_builders import blocker_counter_candle, context_consumption
    from research.strategies.ema_pullback.context.policies import HTF_REGIME_GATE_POLICY

    from research.strategies.ema_pullback.component_builders import context_provider, strategy_contexts

    spec = make_ema_pullback_strategy_spec(
        contexts=strategy_contexts(
            (
                ("htf", context_provider(timeframe="4h", fast_period=100, anchor_period=200, slow_period=1000)),
                ("macro_htf", context_provider(timeframe="1d", fast_period=50, anchor_period=100, slow_period=500)),
            ),
        ),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(
                blocker_htf_regime_gate(context_ref="htf", instance_id="blocker_first"),
                blocker_counter_candle(
                    instance_id="blocker_second",
                    context_consumption=context_consumption(
                        context_ref="macro_htf",
                        policy_id=HTF_REGIME_GATE_POLICY,
                        params=(("allowed_regimes", ["aligned"]),),
                    ),
                ),
            ),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    idx = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    close = pd.Series([100.0], index=idx)
    ohlcv = pd.DataFrame(
        {"close": close, "open": close, "high": close, "low": close, "volume": 1.0},
        index=idx,
    )
    df = add_feature_columns_from_plan(ohlcv, plan)
    bundle = context_bundle_for_spec(spec, df, plan)

    records_df = pd.DataFrame(
        [
            {
                "direction": 0,
                "status": 1,
                "entry_idx": 0,
                "exit_idx": 0,
                "entry_price": 100.0,
                "exit_price": 101.0,
                "size": 1.0,
                "pnl": 1.0,
                "return": 0.01,
            }
        ]
    )

    class _Trades:
        records = records_df

    class _Pf:
        trades = _Trades()

    records = extract_trade_records(
        _Pf(),
        close,
        strategy_spec=spec,
        context_bundle=bundle,
    )
    entry_cc = records[0]["entry_context_consumption"]
    assert entry_cc["instance_id"] == "blocker_second"
    assert entry_cc["context_ref"] == "macro_htf"


def test_trade_entry_consumption_applied_false_when_gate_blocks() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    spec = make_ema_pullback_strategy_spec(
        contexts=htf_strategy_contexts(),
        components=component_stack(
            direction=direction_ema_anchor_stack(),
            blockers=(blocker_htf_regime_gate(allowed_regimes=("aligned",)),),
            trigger=trigger_reclaim_anchor(),
            risk=risk_no_filter(),
        ),
    )
    plan = build_feature_plan_from_strategy_spec(spec)
    idx = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    close = pd.Series([100.0], index=idx)
    ohlcv = pd.DataFrame(
        {"close": close, "open": close, "high": close, "low": close, "volume": 1.0},
        index=idx,
    )
    df = add_feature_columns_from_plan(ohlcv, plan)
    cols = plan.htf_context_columns_for("htf")
    df[cols["fast"]] = [101.0]
    df[cols["anchor"]] = [102.0]
    df[cols["slow"]] = [103.0]
    bundle = context_bundle_for_spec(spec, df, plan)

    records_df = pd.DataFrame(
        [
            {
                "direction": 0,
                "status": 1,
                "entry_idx": 0,
                "exit_idx": 0,
                "entry_price": 100.0,
                "exit_price": 101.0,
                "size": 1.0,
                "pnl": 1.0,
                "return": 0.01,
            }
        ]
    )

    class _Trades:
        records = records_df

    class _Pf:
        trades = _Trades()

    records = extract_trade_records(
        _Pf(),
        close,
        strategy_spec=spec,
        context_bundle=bundle,
    )
    assert records[0]["entry_context_consumption"]["applied"] is False
