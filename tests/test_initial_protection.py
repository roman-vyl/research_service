from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import MarketRange, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import EntryFill
from research_service.execution.protection import resolve_initial_protection


def _evaluation(
    *,
    sl_long: object = "0.02",
    tp_long: object = "0.05",
    sl_short: object = "0.02",
    tp_short: object = "0.05",
    ready_long: bool = True,
    ready_short: bool = True,
) -> StrategyEvaluationResult:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000)
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id="instance-1",
        config_hash="cfg",
        market=market,
        bar_count=1,
        market_data_hash="hash",
        time_ms=(0,),
        entries={"long": (True,), "short": (True,)},
        exit_policy={
            "signal_exit": {"long": [False], "short": [False]},
            "stop_loss_ratio": {"long": [sl_long], "short": [sl_short]},
            "take_profit_ratio": {"long": [tp_long], "short": [tp_short]},
            "stop_ready": {"long": [ready_long], "short": [ready_short]},
        },
        component_evidence={},
        raw={},
    )


def _fill(side: str, *, reference: str = "100", fill: str = "101") -> EntryFill:
    return EntryFill(
        fill_id=f"fill-{side}",
        instance_id="instance-1",
        side=side,
        bar_index=0,
        time_ms=0,
        reference_price=reference,
        fill_price=fill,
        quantity="1",
        slippage_rate="0.01",
    )


def test_long_levels_follow_legacy_ratio_formula() -> None:
    protection = resolve_initial_protection(_evaluation(), _fill("long"))

    assert protection.anchor_price == Decimal("100")
    assert protection.stop_loss_price == Decimal("98.00")
    assert protection.take_profit_price == Decimal("105.00")


def test_short_levels_follow_legacy_ratio_formula() -> None:
    protection = resolve_initial_protection(_evaluation(), _fill("short", fill="99"))

    assert protection.anchor_price == Decimal("100")
    assert protection.stop_loss_price == Decimal("102.00")
    assert protection.take_profit_price == Decimal("95.00")


def test_bbb_profile_anchors_protection_to_signal_close_not_slipped_fill() -> None:
    protection = resolve_initial_protection(_evaluation(), _fill("long", fill="110"))

    assert protection.anchor_price == Decimal("100")
    assert protection.stop_loss_price == Decimal("98.00")
    assert protection.take_profit_price == Decimal("105.00")


def test_absent_stop_or_take_is_preserved() -> None:
    protection = resolve_initial_protection(
        _evaluation(sl_long=None, tp_long=None),
        _fill("long"),
    )

    assert protection.stop_loss_ratio is None
    assert protection.take_profit_ratio is None
    assert protection.stop_loss_price is None
    assert protection.take_profit_price is None


def test_unready_protection_cannot_be_resolved() -> None:
    with pytest.raises(InvalidRequest, match="not ready"):
        resolve_initial_protection(
            _evaluation(ready_long=False),
            _fill("long"),
        )


def test_invalid_ratio_is_rejected() -> None:
    with pytest.raises(InvalidRequest, match="finite and non-negative"):
        resolve_initial_protection(
            _evaluation(sl_long="-0.1"),
            _fill("long"),
        )
