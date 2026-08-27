from __future__ import annotations

from research_service.application.backtests import build_backtest_request
from research_service.domain.contracts import ExplicitRange
from research_service.domain.strategy_instance import DeployableStrategyInstance


def _deployable(enabled: bool = True) -> DeployableStrategyInstance:
    return DeployableStrategyInstance(
        enabled=enabled,
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )


def test_projects_identity_subset_and_drops_enabled() -> None:
    request = build_backtest_request(
        _deployable(),
        range_policy="explicit_range",
        range=ExplicitRange(from_ms=0, to_ms=900_000),
    )

    assert request.strategy.strategy_id == "ema_pullback"
    assert request.strategy.ticker == "BTCUSDT.P"
    assert request.strategy.base_timeframe == "5m"
    assert request.strategy.raw_spec == {"anchor": {"period": 200}}
    assert not hasattr(request.strategy, "enabled")


def test_enabled_value_does_not_affect_the_projected_request() -> None:
    range_ = ExplicitRange(from_ms=0, to_ms=900_000)
    enabled_request = build_backtest_request(
        _deployable(enabled=True), range_policy="explicit_range", range=range_
    )
    disabled_request = build_backtest_request(
        _deployable(enabled=False), range_policy="explicit_range", range=range_
    )

    assert enabled_request.strategy == disabled_request.strategy


def test_full_available_projection_carries_no_range() -> None:
    request = build_backtest_request(_deployable(), range_policy="full_available")

    assert request.range_policy == "full_available"
    assert request.range is None
