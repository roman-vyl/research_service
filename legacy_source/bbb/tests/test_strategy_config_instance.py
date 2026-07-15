"""Runtime execution config tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from research.experiments.config_loader import load_strategy_config
from research.strategies.ema_pullback.component_builders import (
    blocker_counter_candle,
    blocker_extreme_rsi,
    blocker_none,
    component_stack,
    ema_bounce_counter_setup_spec,
    exit_atr_stop_loss,
    exit_atr_take_profit,
    exit_constant_usd_stop_loss,
    exit_constant_usd_take_profit,
    exit_no_signal,
    exit_rsi,
    exit_policy,
    trade_management,
    exits_atr_default,
    trade_sides,
    trigger_reclaim_anchor,
    trigger_touch_anchor,
)
from research.strategies.ema_pullback.config import (
    DEFAULT_FEES,
    DEFAULT_INIT_CASH,
    DEFAULT_SLIPPAGE,
    ExecutionConfig,
    execution_config_from_external,
)
from research.strategies.ema_pullback.cli import parse_args
from research.strategies.ema_pullback.spec import TradeSideSpec, strategy_spec_config_id
from research.strategies.ema_pullback.spec_instances import make_ema_pullback_strategy_spec

from tests.ema_pullback_context_helpers import exit_policy_htf_consumption, htf_strategy_contexts
from tests.test_external_config_loader import _bundle, _instance


def test_execution_config_has_expected_dataclass_fields() -> None:
    cfg = ExecutionConfig(
        family="ema_pullback",
        symbol="ETHUSDT",
        timeframe="4h",
        db_path=Path("x.sqlite"),
        init_cash=DEFAULT_INIT_CASH,
        fees=DEFAULT_FEES,
        slippage=DEFAULT_SLIPPAGE,
    )
    assert set(cfg.__dataclass_fields__) == {
        "family",
        "symbol",
        "timeframe",
        "db_path",
        "init_cash",
        "fees",
        "slippage",
    }


def test_execution_config_validates_runtime_fields() -> None:
    cfg = ExecutionConfig(
        family="ema_pullback",
        symbol="ETHUSDT",
        timeframe="4h",
        db_path=Path("custom.sqlite"),
        init_cash=1500.0,
        fees=0.001,
        slippage=0.0005,
    )
    assert cfg.symbol == "ETHUSDT"
    assert cfg.timeframe == "4h"


def test_runtime_changes_do_not_change_strategy_spec_id() -> None:
    spec = make_ema_pullback_strategy_spec(symbol="BTCUSDT", base_timeframe="1h")
    base_id = strategy_spec_config_id(spec)
    _runtime_a = ExecutionConfig("ema_pullback", "BTCUSDT", "1h", Path("a.sqlite"), 100.0, 0.0, 0.0)
    _runtime_b = ExecutionConfig("ema_pullback", "BTCUSDT", "1h", Path("b.sqlite"), 500.0, 0.001, 0.0005)
    assert strategy_spec_config_id(spec) == base_id


def test_default_strategy_spec_is_long_only() -> None:
    spec = make_ema_pullback_strategy_spec()
    assert spec.trade_sides.enabled == ("long",)


def test_trade_side_spec_accepts_long_and_short() -> None:
    sides = TradeSideSpec(enabled=("long", "short"))
    assert sides.enabled == ("long", "short")
    assert sides.includes("long") is True
    assert sides.includes("short") is True


def test_trade_side_spec_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TradeSideSpec(enabled=())
    with pytest.raises(ValueError, match="one of"):
        TradeSideSpec(enabled=("long", "flat"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="duplicates"):
        TradeSideSpec(enabled=("long", "long"))


def test_trade_sides_are_part_of_strategy_spec_config_id() -> None:
    long_only = make_ema_pullback_strategy_spec(enabled_sides=("long",))
    bidirectional = make_ema_pullback_strategy_spec(enabled_sides=("long", "short"))
    assert long_only.variant == bidirectional.variant
    assert strategy_spec_config_id(long_only) != strategy_spec_config_id(bidirectional)


def test_factory_accepts_sequence_for_enabled_sides() -> None:
    spec = make_ema_pullback_strategy_spec(enabled_sides=["long", "short"])
    assert spec.trade_sides.enabled == ("long", "short")


def test_cli_requires_config_path() -> None:
    with pytest.raises(SystemExit):
        parse_args([])


def test_cli_rejects_legacy_symbol_flag() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--config", "x.yaml", "--symbol", "BTCUSDT"])


def test_cli_accepts_config_and_db_path() -> None:
    args = parse_args(["--config", "experiment.yaml", "--db-path", "custom.sqlite"])
    assert args.config == Path("experiment.yaml")
    assert args.db_path == Path("custom.sqlite")


def test_cli_help_does_not_list_legacy_market_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["-h"])
    out = capsys.readouterr().out
    assert "--symbol" not in out
    assert "--tf" not in out
    assert "--init-cash" not in out
    assert "--fees" not in out
    assert "--slippage" not in out


def test_execution_config_from_external_merges_market_and_optional_execution() -> None:
    payload = {**_bundle([_instance("merge_exec")]), "execution": {}}
    loaded = load_strategy_config(payload)
    spec = loaded.specs[0]
    cfg = execution_config_from_external(
        family=loaded.family,
        symbol=spec.symbol,
        timeframe=spec.base_timeframe,
        db_path=Path("db.sqlite"),
        init_cash=loaded.execution.init_cash,
        fees=loaded.execution.fees,
        slippage=loaded.execution.slippage,
    )
    assert cfg.symbol == "BTCUSDT"
    assert cfg.timeframe == "1h"
    assert cfg.db_path == Path("db.sqlite")
    assert cfg.init_cash == DEFAULT_INIT_CASH
    assert cfg.fees == DEFAULT_FEES
    assert cfg.slippage == DEFAULT_SLIPPAGE


def test_exit_shortcuts_build_expected_component_kinds() -> None:
    no_signal = exit_no_signal()
    rsi = exit_rsi(
        instance_id="rsi_exit_base",
        timeframe="base",
        period=14,
        long_exit_above=80.0,
        short_exit_below=20.0,
    )
    stop = exit_atr_stop_loss(atr_period=14, atr_multiplier=1.5)
    take = exit_atr_take_profit(atr_period=14, atr_multiplier=4.0)
    fixed_sl = exit_constant_usd_stop_loss(usd_distance=500.0)
    fixed_tp = exit_constant_usd_take_profit(usd_distance=1200.0)

    assert (no_signal.component_id, no_signal.exit_kind) == ("no_signal_exit", "signal")
    assert (rsi.component_id, rsi.exit_kind) == ("rsi_signal_exit", "signal")
    assert (stop.component_id, stop.exit_kind) == ("atr_stop_loss", "stop_loss")
    assert (take.component_id, take.exit_kind) == ("atr_take_profit", "take_profit")
    assert (fixed_sl.component_id, fixed_sl.exit_kind) == ("constant_usd_stop_loss", "stop_loss")
    assert (fixed_tp.component_id, fixed_tp.exit_kind) == ("constant_usd_take_profit", "take_profit")
    assert fixed_sl.usd_distance == 500.0 and fixed_sl.distance is None
    assert fixed_tp.usd_distance == 1200.0 and fixed_tp.distance is None
    assert no_signal.instance_id == "no_signal_exit"
    assert rsi.instance_id == "rsi_exit_base"
    assert stop.instance_id == "atr_stop_loss"
    assert take.instance_id == "atr_take_profit"


def test_exits_atr_default_builds_two_distance_exit_rules() -> None:
    exits = exits_atr_default(
        atr_period=14,
        stop_atr_multiplier=1.5,
        take_atr_multiplier=4.0,
    )
    assert len(exits) == 2
    assert [rule.component_id for rule in exits] == ["atr_stop_loss", "atr_take_profit"]
    assert [rule.instance_id for rule in exits] == ["atr_stop_loss", "atr_take_profit"]
    assert [rule.exit_kind for rule in exits] == ["stop_loss", "take_profit"]
    assert [rule.distance.multiplier if rule.distance else None for rule in exits] == [1.5, 4.0]


def test_component_stack_default_matches_baseline_defaults() -> None:
    stack = component_stack()
    assert stack.direction == "ema_anchor_stack_trend"
    assert [b.component_id for b in stack.blockers] == ["no_blockers"]
    assert [b.instance_id for b in stack.blockers] == ["no_blockers"]
    assert len(stack.blockers) >= 1
    assert stack.trigger.component_id == "reclaim_anchor"
    assert stack.risk == "no_risk_filter"


def test_strategy_spec_rejects_mismatched_bounce_params_component_id() -> None:
    from research.strategies.ema_pullback.component_builders import setup_rule

    with pytest.raises(
        ValueError,
        match="UntouchedAnchorSetupSpec",
    ):
        make_ema_pullback_strategy_spec(
            setups=(
                setup_rule(
                    instance_id="bad",
                    component_id="untouched_anchor_setup",
                    params=ema_bounce_counter_setup_spec(),
                ),
            ),
        )


def test_builders_normalize_sequences_to_tuples() -> None:
    sides = trade_sides(["long", "short"])
    blockers_list = [
        blocker_none(),
        blocker_counter_candle(),
        blocker_extreme_rsi(instance_id="rsi_base"),
    ]
    stack = component_stack(blockers=blockers_list, trigger=trigger_touch_anchor())

    assert sides.enabled == ("long", "short")
    assert isinstance(stack.blockers, tuple)
    assert stack.trigger == trigger_touch_anchor()


def test_builders_reject_str_and_bytes_for_sequence_inputs() -> None:
    with pytest.raises(TypeError, match="str/bytes"):
        trade_sides("long")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="str/bytes"):
        component_stack(blockers="no_blockers")  # type: ignore[arg-type]


def test_blocker_and_trigger_shortcuts_return_expected_components() -> None:
    assert blocker_none().component_id == "no_blockers"
    assert blocker_none().instance_id == "no_blockers"
    assert blocker_counter_candle().component_id == "counter_candle_blocker"
    assert (
        blocker_extreme_rsi(instance_id="rsi_base").component_id
        == "rsi_lookback_extreme_blocker"
    )
    from research.strategies.ema_pullback.spec import ReclaimTriggerSpec

    reclaim = trigger_reclaim_anchor()
    assert reclaim.component_id == "reclaim_anchor"
    assert isinstance(reclaim, ReclaimTriggerSpec)
    assert reclaim.lookback == 1
    assert trigger_reclaim_anchor(lookback=2).lookback == 2
    assert trigger_touch_anchor().component_id == "touch_anchor"


def test_make_ema_pullback_strategy_spec_trigger_lookback_default_path() -> None:
    from research.strategies.ema_pullback.spec import ReclaimTriggerSpec

    spec = make_ema_pullback_strategy_spec(trigger_lookback=3)
    assert isinstance(spec.components.trigger, ReclaimTriggerSpec)
    assert spec.components.trigger.lookback == 3


def test_make_ema_pullback_strategy_spec_preserves_custom_components_trigger() -> None:
    from research.strategies.ema_pullback.component_builders import component_stack, trigger_touch_anchor
    from research.strategies.ema_pullback.spec import TriggerSpec

    custom = component_stack(trigger=trigger_touch_anchor())
    spec = make_ema_pullback_strategy_spec(components=custom, trigger_lookback=99)
    assert isinstance(spec.components.trigger, TriggerSpec)
    assert spec.components.trigger.component_id == "touch_anchor"


def test_component_stack_rejects_duplicate_instance_ids_per_role() -> None:
    with pytest.raises(ValueError, match="components.blockers instance_id must be unique"):
        component_stack(
            blockers=(
                blocker_counter_candle(instance_id="duplicate"),
                blocker_extreme_rsi(instance_id="duplicate"),
            )
        )

    with pytest.raises(ValueError, match="globally unique"):
        trade_management(
            exit_policy_spec=exit_policy_htf_consumption(
                always_on=(exit_no_signal(),),
                aligned=(exit_rsi(instance_id="no_signal_exit"),),
            )
        )


def test_repeated_components_require_explicit_distinct_instance_ids() -> None:
    stack = component_stack(
        blockers=(
            blocker_extreme_rsi(instance_id="rsi_5m", timeframe="5m", lookback=20),
            blocker_extreme_rsi(instance_id="rsi_15m", timeframe="15m", lookback=40),
        )
    )

    assert [rule.component_id for rule in stack.blockers] == [
        "rsi_lookback_extreme_blocker",
        "rsi_lookback_extreme_blocker",
    ]
    assert [rule.instance_id for rule in stack.blockers] == ["rsi_5m", "rsi_15m"]
    spec = make_ema_pullback_strategy_spec()
    assert [rule.instance_id for rule in spec.trade_management.exit_policy.always_on.exits] == [
        "atr_stop_loss",
        "atr_take_profit",
    ]
