from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research.experiments.config_loader import (
    ConfigValidationError,
    load_strategy_config,
    load_strategy_config_file,
)
from research.strategies.ema_pullback.execution import runner
from research.strategies.ema_pullback.instance_loader import (
    EmaPullbackInstanceValidationError,
)


def _instance(
    instance_id: str = "baseline",
    *,
    variant: str | None = None,
    fast: int = 100,
    anchor: int = 200,
    slow: int = 1000,
    anchor_source: str = "close",
    anchor_timeframe: str = "base",
    trade_sides: object | None = None,
    exits: object | None = None,
) -> dict[str, object]:
    default_exits = (
        exits
        if exits is not None
        else [
            {
                "instance_id": "atr_stop_loss",
                "component_id": "atr_stop_loss",
                "distance": {"timeframe": "base", "period": 14, "multiplier": 1.5},
            },
            {
                "instance_id": "atr_take_profit",
                "component_id": "atr_take_profit",
                "distance": {"timeframe": "base", "period": 14, "multiplier": 4.0},
            },
        ]
    )
    return {
        "instance_id": instance_id,
        **(
            {"variant": variant}
            if variant is not None
            else {"variant": f"ema_pullback_fast{fast}_anchor{anchor}_slow{slow}"}
        ),
        "market": {"symbol": "BTCUSDT", "base_timeframe": "1h"},
        "strategy": {
            "trade_sides": ["long"] if trade_sides is None else trade_sides,
            "anchor_stack": {
                "source": anchor_source,
                "timeframe": anchor_timeframe,
                "fast": fast,
                "anchor": anchor,
                "slow": slow,
            },
            "direction": {"component_id": "ema_anchor_stack_trend"},
            "setups": [
                {
                    "instance_id": "setup",
                    "component_id": "untouched_anchor_setup",
                    "lookback": 50,
                    "active_bars": 3,
                }
            ],
            "trigger": {"component_id": "reclaim_anchor"},
            "blockers": [{"instance_id": "no_blockers", "component_id": "no_blockers"}],
            "risk": {"component_id": "no_risk_filter"},
            "contexts": {},
            "trade_management": {
                "exit_policy": {
                    "always_on": {"exits": default_exits},
                    "profiles": {
                        "aligned": {"exits": []},
                        "countertrend": {"exits": []},
                        "neutral": {"exits": []},
                    },
                }
            },
        },
    }


def _bundle(instances: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment_id": "ema_ext_smoke",
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0006, "slippage": 0.0001},
        "instances": instances,
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_single_object_external_config() -> None:
    payload = {
        "schema_version": 1,
        "experiment_id": "single",
        "family": "ema_pullback",
        "execution": {"init_cash": 5000.0},
        **_instance("single_baseline"),
    }

    loaded = load_strategy_config(payload)

    assert loaded.experiment_id == "single"
    assert len(loaded.specs) == 1
    assert loaded.entries[0].instance_id == "single_baseline"
    assert loaded.specs[0].symbol == "BTCUSDT"
    assert loaded.specs[0].anchor_stack.fast.source == "close"
    assert loaded.specs[0].anchor_stack.fast.timeframe == "base"
    assert loaded.execution.init_cash == 5000.0


def test_load_bundle_external_config_from_file(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "bundle.json",
        _bundle(
            [
                _instance("baseline"),
                _instance("fast_variant", fast=50, anchor=100, slow=200),
            ]
        ),
    )

    loaded = load_strategy_config_file(path)

    assert [entry.instance_id for entry in loaded.entries] == ["baseline", "fast_variant"]
    assert [spec.anchor_stack.fast.period for spec in loaded.specs] == [100, 50]
    assert loaded.execution.fees == 0.0006
    assert loaded.execution.slippage == 0.0001
    assert loaded.identity_payload()["entries_count"] == 2


@pytest.mark.parametrize("schema_version", [2, "2"])
def test_loader_rejects_unsupported_schema_version(schema_version: object) -> None:
    payload = _bundle([_instance()])
    payload["schema_version"] = schema_version

    with pytest.raises(ConfigValidationError, match="schema_version must be exactly 1"):
        load_strategy_config(payload)


def test_load_external_config_supports_anchor_stack_source_and_timeframe() -> None:
    loaded = load_strategy_config(
        _bundle(
            [
                _instance(
                    "mtf_anchor",
                    anchor_source="close",
                    anchor_timeframe="4h",
                )
            ]
        )
    )

    spec = loaded.specs[0]
    assert spec.anchor_stack.fast.source == "close"
    assert spec.anchor_stack.anchor.source == "close"
    assert spec.anchor_stack.slow.source == "close"
    assert spec.anchor_stack.fast.timeframe == "4h"
    assert spec.anchor_stack.anchor.timeframe == "4h"
    assert spec.anchor_stack.slow.timeframe == "4h"


def test_load_external_config_supports_ema_bounce_counter_setup_without_legacy_emas() -> None:
    instance = _instance("bounce_counter", fast=50, anchor=200, slow=500)
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["setups"] = [
        {
            "instance_id": "bounce_counter",
            "component_id": "ema_bounce_counter_setup",
            "params": {
                "max_bounces": 3,
                "raw_touch_mode": "range_cross",
                "touch_lookback_bars": 10,
                "trend_start_confirmation_bars": 1,
                "trend_break_confirmation_bars": 1,
            },
        }
    ]

    loaded = load_strategy_config(_bundle([instance]))
    spec = loaded.specs[0]

    assert spec.setups[0].component_id == "ema_bounce_counter_setup"
    assert spec.setups[0].params.max_bounces == 3
    assert spec.anchor_stack.fast.period == 50
    assert loaded.entries[0].strategy_spec_config_id


def test_load_external_config_accepts_legacy_bounce_emas_matching_anchor_stack() -> None:
    instance = _instance("bounce_counter", fast=50, anchor=200, slow=500)
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["setups"] = [
        {
            "instance_id": "bounce_counter",
            "component_id": "ema_bounce_counter_setup",
            "params": {
                "fast_ema": 50,
                "anchor_ema": 200,
                "slow_ema": 500,
                "max_bounces": 3,
            },
        }
    ]

    loaded = load_strategy_config(_bundle([instance]))
    assert loaded.specs[0].setups[0].params.max_bounces == 3


def test_load_external_config_rejects_legacy_bounce_emas_mismatching_anchor_stack() -> None:
    instance = _instance("bounce_counter", fast=100, anchor=200, slow=1000)
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["setups"] = [
        {
            "instance_id": "bounce_counter",
            "component_id": "ema_bounce_counter_setup",
            "params": {
                "fast_ema": 50,
                "anchor_ema": 200,
                "slow_ema": 500,
                "max_bounces": 3,
            },
        }
    ]

    with pytest.raises(EmaPullbackInstanceValidationError, match="legacy setup EMA params"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_rejects_legacy_bounce_htf_emas_mismatching_anchor_stack() -> None:
    instance = _instance("bounce_counter_htf", fast=100, anchor=200, slow=1000)
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["setups"] = [
        {
            "instance_id": "bounce_counter",
            "component_id": "ema_bounce_counter_setup",
            "params": {
                "fast_ema": {"source": "close", "timeframe": "4h", "period": 50},
                "anchor_ema": 200,
                "slow_ema": 500,
            },
        }
    ]

    with pytest.raises(EmaPullbackInstanceValidationError, match="legacy setup EMA params"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_supports_exit_atr_distance_timeframe() -> None:
    instance = _instance("mtf_exit_distance")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    trade_management = strategy["trade_management"]
    assert isinstance(trade_management, dict)
    exits = trade_management["exit_policy"]["always_on"]["exits"]
    assert isinstance(exits, list)
    exits[0]["distance"]["timeframe"] = "15m"

    loaded = load_strategy_config(_bundle([instance]))

    spec = loaded.specs[0]
    rule = spec.trade_management.exit_policy.always_on.exits[0]
    assert rule.distance is not None
    assert rule.distance.timeframe == "15m"


def test_load_external_config_supports_constant_usd_stop_and_take() -> None:
    loaded = load_strategy_config(
        _bundle(
            [
                _instance(
                    "constant_usd_exits",
                    exits=[
                        {
                            "instance_id": "sl_usd",
                            "component_id": "constant_usd_stop_loss",
                            "usd_distance": 500.0,
                        },
                        {
                            "instance_id": "tp_usd",
                            "component_id": "constant_usd_take_profit",
                            "usd_distance": 1200.0,
                        },
                    ],
                )
            ]
        )
    )

    sl, tp = loaded.specs[0].trade_management.exit_policy.always_on.exits
    assert sl.component_id == "constant_usd_stop_loss" and sl.usd_distance == 500.0 and sl.distance is None
    assert tp.component_id == "constant_usd_take_profit" and tp.usd_distance == 1200.0 and tp.distance is None


def test_load_external_config_supports_only_atr_stop_loss_exit() -> None:
    loaded = load_strategy_config(
        _bundle(
            [
                _instance(
                    "only_atr_sl",
                    exits=[
                        {
                            "instance_id": "atr_stop_loss",
                            "component_id": "atr_stop_loss",
                            "distance": {"timeframe": "base", "period": 14, "multiplier": 1.5},
                        }
                    ],
                )
            ]
        )
    )

    exit_rule = loaded.specs[0].trade_management.exit_policy.always_on.exits[0]
    assert len(loaded.specs[0].trade_management.exit_policy.always_on.exits) == 1
    assert exit_rule.exit_kind == "stop_loss"
    assert exit_rule.distance is not None
    assert exit_rule.distance.period == 14
    assert exit_rule.distance.multiplier == 1.5


def test_load_external_config_supports_only_atr_take_profit_exit() -> None:
    loaded = load_strategy_config(
        _bundle(
            [
                _instance(
                    "only_atr_tp",
                    exits=[
                        {
                            "instance_id": "atr_take_profit",
                            "component_id": "atr_take_profit",
                            "distance": {"timeframe": "base", "period": 14, "multiplier": 4.0},
                        }
                    ],
                )
            ]
        )
    )

    exit_rule = loaded.specs[0].trade_management.exit_policy.always_on.exits[0]
    assert len(loaded.specs[0].trade_management.exit_policy.always_on.exits) == 1
    assert exit_rule.exit_kind == "take_profit"
    assert exit_rule.distance is not None
    assert exit_rule.distance.period == 14
    assert exit_rule.distance.multiplier == 4.0


def test_load_external_config_supports_only_rsi_signal_exit() -> None:
    loaded = load_strategy_config(
        _bundle(
            [
                _instance(
                    "only_rsi_exit",
                    exits=[
                        {
                            "instance_id": "rsi_exit",
                            "component_id": "rsi_signal_exit",
                            "rsi": {"timeframe": "base", "period": 14},
                            "long_exit_above": 70.0,
                            "short_exit_below": 30.0,
                        }
                    ],
                )
            ]
        )
    )

    exit_rule = loaded.specs[0].trade_management.exit_policy.always_on.exits[0]
    assert len(loaded.specs[0].trade_management.exit_policy.always_on.exits) == 1
    assert exit_rule.exit_kind == "signal"
    assert exit_rule.distance is None
    assert exit_rule.rsi is not None
    assert exit_rule.rsi.timeframe == "base"
    assert exit_rule.rsi.period == 14
    assert exit_rule.long_exit_above == 70.0
    assert exit_rule.short_exit_below == 30.0


def test_load_external_config_accepts_user_variant_label() -> None:
    loaded = load_strategy_config(_bundle([_instance("baseline_long", variant="baseline_long")]))

    assert loaded.specs[0].variant == "baseline_long"


def test_load_external_config_derives_variant_when_omitted() -> None:
    instance = _instance("derived_variant", fast=21, anchor=55, slow=200)
    instance.pop("variant")

    loaded = load_strategy_config(_bundle([instance]))

    assert loaded.specs[0].variant == "ema_pullback_fast21_anchor55_slow200"


def test_load_external_config_accepts_enabled_trade_sides_mapping() -> None:
    loaded = load_strategy_config(
        _bundle([_instance("enabled_mapping", trade_sides={"enabled": ["long", "short"]})])
    )

    assert loaded.specs[0].trade_sides.enabled == ("long", "short")


def test_load_external_config_accepts_ui_friendly_trade_side_flags() -> None:
    loaded = load_strategy_config(
        _bundle([_instance("side_flags", trade_sides={"long": True, "short": False})])
    )

    assert loaded.specs[0].trade_sides.enabled == ("long",)


def test_load_external_config_rejects_non_bool_trade_side_flags() -> None:
    with pytest.raises(EmaPullbackInstanceValidationError, match="strategy.trade_sides.long"):
        load_strategy_config(_bundle([_instance("bad_side_flags", trade_sides={"long": "yes"})]))


def test_load_external_config_rejects_pullback_to_anchor_setup_id() -> None:
    instance = _instance("setup_legacy")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy.pop("setups", None)
    strategy["setup"] = {
        "component_id": "pullback_to_anchor",
        "lookback": 50,
        "active_bars": 3,
    }

    with pytest.raises(EmaPullbackInstanceValidationError, match="pullback_to_anchor"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_reclaim_anchor_accepts_lookback() -> None:
    instance = _instance("reclaim_lb")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "reclaim_anchor", "lookback": 3}

    loaded = load_strategy_config(_bundle([instance]))
    trigger = loaded.specs[0].components.trigger
    from research.strategies.ema_pullback.spec import ReclaimTriggerSpec

    assert isinstance(trigger, ReclaimTriggerSpec)
    assert trigger.lookback == 3


def test_load_external_config_reclaim_anchor_default_lookback() -> None:
    loaded = load_strategy_config(_bundle([_instance("reclaim_default")]))
    trigger = loaded.specs[0].components.trigger
    from research.strategies.ema_pullback.spec import ReclaimTriggerSpec

    assert isinstance(trigger, ReclaimTriggerSpec)
    assert trigger.lookback == 1


def test_load_external_config_reclaim_anchor_rejects_non_positive_lookback() -> None:
    instance = _instance("reclaim_bad_lb")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "reclaim_anchor", "lookback": 0}

    with pytest.raises(EmaPullbackInstanceValidationError, match="lookback"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_strong_reclaim_anchor_accepts_lookback() -> None:
    instance = _instance("strong_reclaim_lb")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "strong_reclaim_anchor", "lookback": 3}

    loaded = load_strategy_config(_bundle([instance]))
    trigger = loaded.specs[0].components.trigger
    from research.strategies.ema_pullback.spec import StrongReclaimTriggerSpec

    assert isinstance(trigger, StrongReclaimTriggerSpec)
    assert trigger.lookback == 3


def test_load_external_config_strong_reclaim_anchor_default_lookback() -> None:
    instance = _instance("strong_reclaim_default")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "strong_reclaim_anchor"}

    loaded = load_strategy_config(_bundle([instance]))
    trigger = loaded.specs[0].components.trigger
    from research.strategies.ema_pullback.spec import StrongReclaimTriggerSpec

    assert isinstance(trigger, StrongReclaimTriggerSpec)
    assert trigger.lookback == 1


def test_load_external_config_strong_reclaim_anchor_rejects_non_positive_lookback() -> None:
    instance = _instance("strong_reclaim_bad_lb")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "strong_reclaim_anchor", "lookback": 0}

    with pytest.raises(EmaPullbackInstanceValidationError, match="lookback"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_touch_anchor_rejects_lookback() -> None:
    instance = _instance("touch_lb")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["trigger"] = {"component_id": "touch_anchor", "lookback": 1}

    with pytest.raises(EmaPullbackInstanceValidationError, match="unknown field"):
        load_strategy_config(_bundle([instance]))


def test_load_external_config_rejects_component_alias() -> None:
    instance = _instance("component_alias")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    trigger = strategy["trigger"]
    assert isinstance(trigger, dict)
    trigger.pop("component_id")
    trigger["component"] = "reclaim_anchor"

    with pytest.raises(EmaPullbackInstanceValidationError, match="component"):
        load_strategy_config(_bundle([instance]))


def test_loader_rejects_duplicate_instance_ids() -> None:
    with pytest.raises(ConfigValidationError, match="duplicate instance_id"):
        load_strategy_config(_bundle([_instance("dup"), _instance("dup")]))


def test_loader_rejects_unknown_envelope_fields_in_bundle() -> None:
    payload = _bundle([_instance()])
    payload["unexpected"] = True

    with pytest.raises(ConfigValidationError, match="unknown envelope field"):
        load_strategy_config(payload)


def test_loader_rejects_unsupported_family_before_dispatch() -> None:
    payload = _bundle([_instance()])
    payload["family"] = "other_family"

    with pytest.raises(ConfigValidationError, match="unsupported family"):
        load_strategy_config(payload)


def test_loader_rejects_unknown_run_level_execution_fields() -> None:
    payload = _bundle([_instance()])
    execution = payload["execution"]
    assert isinstance(execution, dict)
    execution["leverage"] = 2

    with pytest.raises(ConfigValidationError, match="unknown execution field"):
        load_strategy_config(payload)


def test_instance_loader_rejects_unknown_family_fields() -> None:
    payload = _bundle([_instance()])
    payload["instances"][0]["strategy"]["family_extra"] = "bad"  # type: ignore[index]

    with pytest.raises(EmaPullbackInstanceValidationError, match="unknown field"):
        load_strategy_config(payload)


def test_instance_loader_rejects_external_config_id_alias() -> None:
    instance = _instance()
    instance.pop("instance_id")
    instance["external_config_id"] = "legacy"

    with pytest.raises(ConfigValidationError, match="external_config_id"):
        load_strategy_config(_bundle([instance]))


def test_instance_loader_rejects_instance_level_execution() -> None:
    instance = _instance()
    instance["execution"] = {"init_cash": 10000.0}

    with pytest.raises(EmaPullbackInstanceValidationError, match="unknown field"):
        load_strategy_config(_bundle([instance]))


def test_runner_does_not_load_candles_when_config_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_instance = _instance()
    strategy = bad_instance["strategy"]
    assert isinstance(strategy, dict)
    strategy.pop("anchor_stack")
    path = _write_json(tmp_path / "bad.json", _bundle([bad_instance]))
    called = False

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("load_candles_once must not run on invalid config")

    monkeypatch.setattr(runner, "load_candles_once", fail_if_called)

    with pytest.raises(EmaPullbackInstanceValidationError, match="anchor_stack is required"):
        runner.run_strategy_specs_from_config(path)
    assert called is False


def test_runner_applies_run_level_execution_from_external_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_json(tmp_path / "good.json", _bundle([_instance()]))
    captured: dict[str, float] = {}

    monkeypatch.setattr(
        runner,
        "load_candles_once",
        lambda _cfg: SimpleNamespace(
            ohlcv=object(),
            candles_count=1,
            from_open_time_ms=1,
            to_open_time_ms=2,
        ),
    )

    def fake_run_strategy_spec(
        _spec: object,
        _ohlcv: object,
        *,
        init_cash: float,
        fees: float,
        slippage: float,
    ) -> object:
        captured.update({"init_cash": init_cash, "fees": fees, "slippage": slippage})
        return SimpleNamespace(to_payload=lambda: {"variant": "fake"})

    monkeypatch.setattr(runner, "run_strategy_spec", fake_run_strategy_spec)
    monkeypatch.setattr(runner, "comparison_row", lambda _result: {})
    monkeypatch.setattr(runner, "print_comparison_table", lambda _rows: None)
    monkeypatch.setattr(
        runner,
        "write_research_results",
        lambda _payload: (
            runner._ROOT / "research" / "results" / "latest.json",
            runner._ROOT / "research" / "results" / "runs" / "fake.json",
            runner._ROOT / "research" / "results" / "runs" / "fake.summary.json",
        ),
    )

    runner.run_strategy_specs_from_config(path)

    assert captured == {"init_cash": 10000.0, "fees": 0.0006, "slippage": 0.0001}


def test_load_external_config_supports_trend_strength_episode_blocker() -> None:
    instance = _instance("trend_strength_blocker")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
            "timeframe": "base",
            "adx_period": 14,
            "min_adx_peak": 25,
            "peak_lookback_bars": 60,
            "max_bars_since_peak": 40,
            "min_current_adx": 12,
        }
    ]

    loaded = load_strategy_config(_bundle([instance]))
    rule = loaded.specs[0].components.blockers[0]

    assert rule.component_id == "trend_strength_episode_blocker"
    assert rule.trend_strength is not None
    assert rule.trend_strength.min_adx_peak == 25.0
    assert rule.trend_strength.peak_lookback_bars == 60


def test_load_external_config_parses_trend_strength_bool_false_string() -> None:
    instance = _instance("trend_strength_bool")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
            "require_di_alignment_on_peak": "false",
            "block_on_opposite_di_flip": "false",
        }
    ]

    loaded = load_strategy_config(_bundle([instance]))
    params = loaded.specs[0].components.blockers[0].trend_strength
    assert params is not None
    assert params.require_di_alignment_on_peak is False
    assert params.block_on_opposite_di_flip is False


def test_load_trend_strength_defaults_true_when_bool_keys_omitted() -> None:
    instance = _instance("trend_strength_defaults")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
        }
    ]
    loaded = load_strategy_config(_bundle([instance]))
    params = loaded.specs[0].components.blockers[0].trend_strength
    assert params is not None
    assert params.require_di_alignment_on_peak is True
    assert params.block_on_opposite_di_flip is True


def test_load_trend_strength_honors_explicit_false_bools() -> None:
    instance = _instance("trend_strength_false")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
            "require_di_alignment_on_peak": False,
            "block_on_opposite_di_flip": False,
        }
    ]
    loaded = load_strategy_config(_bundle([instance]))
    params = loaded.specs[0].components.blockers[0].trend_strength
    assert params is not None
    assert params.require_di_alignment_on_peak is False
    assert params.block_on_opposite_di_flip is False


def test_load_external_config_ignores_legacy_require_ema_stack_direction() -> None:
    instance = _instance("trend_strength_legacy_ema")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
            "require_ema_stack_direction": "false",
        }
    ]

    loaded = load_strategy_config(_bundle([instance]))
    params = loaded.specs[0].components.blockers[0].trend_strength
    assert params is not None
    assert not hasattr(params, "require_ema_stack_direction")


def test_load_external_config_rejects_htf_trend_strength_timeframe() -> None:
    instance = _instance("trend_strength_htf")
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    strategy["blockers"] = [
        {
            "instance_id": "trend_strength",
            "component_id": "trend_strength_episode_blocker",
            "timeframe": "1h",
        }
    ]

    with pytest.raises(EmaPullbackInstanceValidationError, match="MVP requires timeframe"):
        load_strategy_config(_bundle([instance]))


def test_instance_loader_rejects_top_level_component_shape() -> None:
    instance = _instance()
    strategy = instance["strategy"]
    assert isinstance(strategy, dict)
    instance["anchor_stack"] = strategy.pop("anchor_stack")

    with pytest.raises(EmaPullbackInstanceValidationError, match="unknown field"):
        load_strategy_config(_bundle([instance]))

