from __future__ import annotations

from decimal import Decimal

import pytest

from research_service.domain.contracts import (
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    InitialProtectionLegDTO,
    MarketRange,
    PartialTakeLegDTO,
    StrategyEvaluationResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import EntryFill
from research_service.execution.projection_entry import resolve_initial_protection_from_opportunity
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


# --- frozen partial take legs (research-frozen-partial-take-ladder-v1 group 3) --

def _opportunity(side: str, *legs: tuple[str, float, float], take: float | None = 0.08):
    return ExecutableEntryOpportunityDTO(
        bar_index=0,
        side=side,
        locked_exit_profile="aligned",
        initial_stop=InitialProtectionLegDTO(
            ratio=0.05,
            attribution=ExitAttributionDTO(rule_id="sl", component_id="c", exit_kind="stop_loss"),
        ),
        initial_take=None
        if take is None
        else InitialProtectionLegDTO(
            ratio=take,
            attribution=ExitAttributionDTO(rule_id="tp", component_id="c", exit_kind="take_profit"),
        ),
        partial_takes=tuple(
            PartialTakeLegDTO(
                take_id=take_id,
                ratio=ratio,
                fraction_of_initial=fraction,
                attribution=ExitAttributionDTO(
                    rule_id=take_id, component_id="pct_partial_take", exit_kind="partial_take"
                ),
            )
            for take_id, ratio, fraction in legs
        ),
    )


def _q0_fill(side: str, quantity: str = "100") -> EntryFill:
    return EntryFill(
        fill_id="entry-1",
        instance_id="i1",
        side=side,
        bar_index=0,
        time_ms=0,
        reference_price=Decimal("100"),
        fill_price=Decimal("100"),
        quantity=Decimal(quantity),
        slippage_rate=Decimal("0"),
    )


def test_long_leg_level_and_quantity_are_frozen_at_entry() -> None:
    protection = resolve_initial_protection_from_opportunity(
        _opportunity("long", ("pt1", 0.01, 0.25)), _q0_fill("long")
    )
    (leg,) = protection.partial_takes
    assert (leg.take_id, leg.level, leg.quantity) == ("pt1", Decimal("101.00"), Decimal("25.00"))
    assert leg.fraction_of_initial == Decimal("0.25")
    assert leg.attribution.exit_kind == "partial_take"
    assert leg.attribution.component_id == "pct_partial_take"


def test_short_leg_levels_mirror_long() -> None:
    protection = resolve_initial_protection_from_opportunity(
        _opportunity("short", ("pt1", 0.01, 0.25), ("pt3", 0.03, 0.25)), _q0_fill("short")
    )
    assert [(leg.level, leg.quantity) for leg in protection.partial_takes] == [
        (Decimal("99.00"), Decimal("25.00")),
        (Decimal("97.00"), Decimal("25.00")),
    ]


def test_leg_quantity_is_not_rounded() -> None:
    protection = resolve_initial_protection_from_opportunity(
        _opportunity("long", ("pt1", 0.01, 0.333)), _q0_fill("long", quantity="0.017")
    )
    assert protection.partial_takes[0].quantity == Decimal("0.005661")


def test_leg_beyond_final_take_is_stored_without_comparison() -> None:
    protection = resolve_initial_protection_from_opportunity(
        _opportunity("long", ("pt10", 0.10, 0.25), take=0.08), _q0_fill("long")
    )
    assert protection.take_profit_price == Decimal("108.00")
    assert protection.partial_takes[0].level == Decimal("110.00")


def test_non_positive_short_leg_level_fails_closed() -> None:
    with pytest.raises(InvalidRequest, match="partial take"):
        resolve_initial_protection_from_opportunity(
            _opportunity("short", ("pt", 1.0, 0.25)), _q0_fill("short")
        )


def test_protection_without_legs_is_unchanged() -> None:
    protection = resolve_initial_protection_from_opportunity(
        _opportunity("long"), _q0_fill("long")
    )
    assert protection.partial_takes == ()
    assert protection.stop_loss_price == Decimal("95.00")
    assert protection.take_profit_price == Decimal("108.00")
