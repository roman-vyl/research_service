from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_service.domain.strategy_instance import (
    DeployableStrategyInstance,
    StrategyInstanceIdentity,
    derive_strategy_instance_id,
)


def test_identity_derivation_is_deterministic() -> None:
    kwargs = dict(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )
    assert derive_strategy_instance_id(**kwargs) == derive_strategy_instance_id(**kwargs)


def test_identity_derivation_ignores_raw_spec_key_order() -> None:
    a = derive_strategy_instance_id(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"a": 1, "b": 2},
    )
    b = derive_strategy_instance_id(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"b": 2, "a": 1},
    )
    assert a == b


def test_identity_derivation_changes_with_any_identity_field() -> None:
    base = derive_strategy_instance_id(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )
    assert (
        derive_strategy_instance_id(
            strategy_id="ema_pullback",
            ticker="ETHUSDT.P",
            base_timeframe="5m",
            raw_spec={"anchor": {"period": 200}},
        )
        != base
    )
    assert (
        derive_strategy_instance_id(
            strategy_id="ema_pullback",
            ticker="BTCUSDT.P",
            base_timeframe="1h",
            raw_spec={"anchor": {"period": 200}},
        )
        != base
    )
    assert (
        derive_strategy_instance_id(
            strategy_id="ema_pullback",
            ticker="BTCUSDT.P",
            base_timeframe="5m",
            raw_spec={"anchor": {"period": 500}},
        )
        != base
    )


def test_deployable_instance_identity_excludes_enabled() -> None:
    enabled = DeployableStrategyInstance(
        enabled=True,
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )
    disabled = enabled.model_copy(update={"enabled": False})

    assert enabled.identity() == disabled.identity()
    assert (
        derive_strategy_instance_id(
            strategy_id=enabled.strategy_id,
            ticker=enabled.ticker,
            base_timeframe=enabled.base_timeframe,
            raw_spec=enabled.raw_spec,
        )
        == derive_strategy_instance_id(
            strategy_id=disabled.strategy_id,
            ticker=disabled.ticker,
            base_timeframe=disabled.base_timeframe,
            raw_spec=disabled.raw_spec,
        )
    )


def test_deployable_instance_projects_identity_subset_only() -> None:
    document = DeployableStrategyInstance(
        enabled=True,
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )
    identity = document.identity()
    assert isinstance(identity, StrategyInstanceIdentity)
    assert not hasattr(identity, "enabled")


@pytest.mark.parametrize("model_cls", [StrategyInstanceIdentity, DeployableStrategyInstance])
@pytest.mark.parametrize("legacy_field", ["instance_id", "family", "variant", "strategy_version"])
def test_legacy_fields_are_rejected(model_cls, legacy_field: str) -> None:
    payload = {
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {},
        legacy_field: "unexpected",
    }
    if model_cls is DeployableStrategyInstance:
        payload["enabled"] = True

    with pytest.raises(ValidationError):
        model_cls.model_validate(payload)


def test_identity_missing_strategy_id_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyInstanceIdentity.model_validate(
            {"ticker": "BTCUSDT.P", "base_timeframe": "5m", "raw_spec": {}}
        )


def test_identity_unsupported_timeframe_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyInstanceIdentity.model_validate(
            {
                "strategy_id": "ema_pullback",
                "ticker": "BTCUSDT.P",
                "base_timeframe": "3m",
                "raw_spec": {},
            }
        )


def test_identity_ticker_pattern_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyInstanceIdentity.model_validate(
            {
                "strategy_id": "ema_pullback",
                "ticker": "btcusdt",
                "base_timeframe": "5m",
                "raw_spec": {},
            }
        )
