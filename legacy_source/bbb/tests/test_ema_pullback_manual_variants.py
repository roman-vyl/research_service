from __future__ import annotations

from research.strategies.ema_pullback.component_builders import (
    anchor_stack_from_periods,
    blocker_counter_candle,
    component_stack,
    exit_policy,
    exit_no_signal,
    exit_rsi,
    exits_atr_default,
    trade_management,
    trigger_touch_anchor,
)
from research.strategies.ema_pullback.spec import strategy_spec_config_id
from research.strategies.ema_pullback.spec_instances import (
    make_ema_pullback_strategy_spec,
    variant_from_spec,
)


def test_spec_instance_factory_values() -> None:
    reference = make_ema_pullback_strategy_spec()
    spec = make_ema_pullback_strategy_spec(symbol="ethusdt", base_timeframe="4h")
    assert spec.variant == reference.variant
    assert spec.variant == variant_from_spec(spec)
    assert spec.symbol == "ETHUSDT"
    assert spec.base_timeframe == "4h"
    assert spec.setups[0].params.lookback == reference.setups[0].params.lookback
    assert spec.setups[0].params.active_bars == reference.setups[0].params.active_bars
    assert spec.anchor_stack == reference.anchor_stack
    assert spec.trade_management == reference.trade_management
    assert {r.exit_kind for r in spec.trade_management.exit_policy.always_on.exits} == {
        "stop_loss",
        "take_profit",
    }


def test_baseline_factory_matches_expected_stack_shape() -> None:
    spec = make_ema_pullback_strategy_spec(symbol="BTCUSDT", base_timeframe="1h")
    assert spec == make_ema_pullback_strategy_spec()
    assert spec.variant == variant_from_spec(spec)
    assert (
        spec.anchor_stack.fast.period
        < spec.anchor_stack.anchor.period
        < spec.anchor_stack.slow.period
    )
    assert spec.components.direction == "ema_anchor_stack_trend"
    assert [b.component_id for b in spec.components.blockers] == ["no_blockers"]
    assert spec.setups[0].component_id == "untouched_anchor_setup"
    assert spec.components.trigger.component_id == "reclaim_anchor"
    assert [e.component_id for e in spec.trade_management.exit_policy.always_on.exits] == [
        "atr_stop_loss",
        "atr_take_profit",
    ]
    assert spec.components.risk == "no_risk_filter"


def test_custom_spec_variant_follows_anchor_stack_periods() -> None:
    spec = make_ema_pullback_strategy_spec(fast_period=7, anchor_period=11, slow_period=13)
    assert spec.variant == variant_from_spec(spec)
    assert spec.anchor_stack.fast.period == 7
    assert spec.anchor_stack.anchor.period == 11
    assert spec.anchor_stack.slow.period == 13


def test_factory_accepts_user_variant_label() -> None:
    spec = make_ema_pullback_strategy_spec(variant="baseline_both")

    assert spec.variant == "baseline_both"
    assert variant_from_spec(spec) == "ema_pullback_fast100_anchor200_slow1000"


def test_anchor_stack_builder_matches_factory_anchor_periods() -> None:
    spec = make_ema_pullback_strategy_spec(fast_period=21, anchor_period=55, slow_period=200)
    expected = anchor_stack_from_periods(fast=21, anchor=55, slow=200)
    assert spec.anchor_stack == expected


def test_factory_accepts_anchor_stack_source_and_timeframe() -> None:
    spec = make_ema_pullback_strategy_spec(
        fast_period=21,
        anchor_period=55,
        slow_period=200,
        anchor_source="close",
        anchor_timeframe="4h",
    )
    expected = anchor_stack_from_periods(
        fast=21,
        anchor=55,
        slow=200,
        source="close",
        timeframe="4h",
    )
    assert spec.anchor_stack == expected


def test_factory_uses_default_atr_exit_shortcuts_in_expected_order() -> None:
    spec = make_ema_pullback_strategy_spec(
        atr_period=21,
        stop_atr_multiplier=2.0,
        take_atr_multiplier=5.0,
    )
    expected_exits = exits_atr_default(
        atr_period=21,
        stop_atr_multiplier=2.0,
        take_atr_multiplier=5.0,
    )
    assert spec.trade_management.exit_policy.always_on.exits == expected_exits


def test_factory_accepts_custom_components_as_source_of_truth() -> None:
    custom_components = component_stack(
        trigger=trigger_touch_anchor(),
        blockers=(blocker_counter_candle(),),
    )
    custom_tm = trade_management(
        exit_policy_spec=exit_policy(
            always_on=(
                exit_no_signal(),
                exit_rsi(instance_id="rsi_exit_base", long_exit_above=75.0, short_exit_below=25.0),
            ),
            aligned=(),
            countertrend=(),
            neutral=(),
        )
    )
    spec = make_ema_pullback_strategy_spec(
        atr_period=99,
        stop_atr_multiplier=9.9,
        take_atr_multiplier=9.8,
        components=custom_components,
        trade_management_spec=custom_tm,
    )
    assert spec.components == custom_components
    assert spec.trade_management == custom_tm
    assert spec.components.trigger.component_id == "touch_anchor"
    assert [b.component_id for b in spec.components.blockers] == ["counter_candle_blocker"]
    assert [e.component_id for e in spec.trade_management.exit_policy.always_on.exits] == [
        "no_signal_exit",
        "rsi_signal_exit",
    ]


def test_factory_does_not_override_custom_exits_with_atr_defaults() -> None:
    custom_tm = trade_management(
        exit_policy_spec=exit_policy(
            always_on=(exit_no_signal(),),
            aligned=(),
            countertrend=(),
            neutral=(),
        )
    )
    spec = make_ema_pullback_strategy_spec(
        atr_period=14,
        stop_atr_multiplier=1.5,
        take_atr_multiplier=4.0,
        trade_management_spec=custom_tm,
    )
    assert [e.component_id for e in spec.trade_management.exit_policy.always_on.exits] == [
        "no_signal_exit"
    ]


def test_factory_baseline_components_remain_default_without_custom_override() -> None:
    spec = make_ema_pullback_strategy_spec()
    assert spec.components == component_stack()


def test_factory_custom_and_baseline_components_produce_different_config_ids() -> None:
    baseline = make_ema_pullback_strategy_spec()
    custom = make_ema_pullback_strategy_spec(
        components=component_stack(
            trigger=trigger_touch_anchor(),
            blockers=(blocker_counter_candle(),),
        )
    )
    assert baseline.variant == custom.variant
    assert strategy_spec_config_id(baseline) != strategy_spec_config_id(custom)
