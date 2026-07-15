from decimal import Decimal

import pytest

from research_service.domain.contracts import Candle, MarketRange, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import (
    EntryFill,
    ExitCandidate,
    InitialProtection,
    PositionState,
)
from research_service.execution.managed_policy import ManagedEffectiveState
from research_service.execution.unified_exits import (
    arbitrate_unified_exit_candidates,
    collect_unified_exit_candidates,
    execute_unified_exit,
)


def evaluation(*, signal: bool = True) -> StrategyEvaluationResult:
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="i1",
        config_hash="cfg",
        market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000),
        bar_count=2,
        market_data_hash="market",
        time_ms=(0, 300_000),
        entries={"long": (True, False), "short": (False, False)},
        exit_policy={
            "signal_exit": {"long": (False, signal), "short": (False, False)},
            "stop_loss_ratio": {"long": ("0.02", "0.02"), "short": ("0.02", "0.02")},
            "take_profit_ratio": {"long": ("0.05", "0.05"), "short": ("0.05", "0.05")},
            "stop_ready": {"long": (True, True), "short": (True, True)},
        },
        component_evidence={},
        raw={},
    )


def position() -> PositionState:
    return PositionState(
        position_id="p1",
        instance_id="i1",
        side="long",
        entry_fill=EntryFill(
            fill_id="entry-1",
            instance_id="i1",
            side="long",
            bar_index=0,
            time_ms=0,
            reference_price="100",
            fill_price="100",
            quantity="1",
            slippage_rate="0",
        ),
        initial_protection=InitialProtection(
            side="long",
            source_bar_index=0,
            source_time_ms=0,
            anchor_price="100",
            stop_loss_ratio="0.02",
            take_profit_ratio="0.05",
            stop_loss_price="98",
            take_profit_price="105",
        ),
    )


def managed_state(*, take_profile: str = "initial") -> ManagedEffectiveState:
    return ManagedEffectiveState(
        trade_id="p1",
        side="long",
        effective_time_ms=300_000,
        source_bar_index=0,
        source_time_ms=0,
        phase="protected",
        bars_in_trade=1,
        mfe_pct="0.02",
        mae_pct="0.01",
        active_stop_price="99",
        active_stop_rule_id="be",
        active_stop_component_id="break_even_stop",
        active_take_profile=take_profile,
        runtime_exit_rule_ids=("protect", "take", "close"),
        runtime_exit_components={
            "protect": "phase_runtime_exit",
            "take": "phase_runtime_exit",
            "close": "phase_runtime_exit",
        },
        runtime_exit_kinds={
            "protect": "protective_exit",
            "take": "take_profit",
            "close": "market_close",
        },
    )


def candle() -> Candle:
    return Candle(
        open_time_ms=300_000,
        open="100",
        high="106",
        low="97",
        close="103",
        volume="1",
    )


def test_unified_priority_matches_legacy_order() -> None:
    candidates = collect_unified_exit_candidates(
        evaluation(), position(), candle(), managed_state(), bar_index=1
    )
    result = arbitrate_unified_exit_candidates(candidates)
    assert result.winner is not None
    assert result.winner.candidate_type == "stop_loss"
    assert [c.candidate_type for c in result.losing_candidates] == [
        "managed_stop",
        "take_profit",
        "runtime_protective",
        "runtime_take",
        "runtime_close",
        "signal",
    ]


def test_disable_initial_tp_suppresses_only_static_take() -> None:
    candidates = collect_unified_exit_candidates(
        evaluation(),
        position(),
        candle(),
        managed_state(take_profile="disable_initial_tp"),
        bar_index=1,
    )
    types = [candidate.candidate_type for candidate in candidates]
    assert "take_profit" not in types
    assert "stop_loss" in types
    assert "managed_stop" in types
    assert "runtime_take" in types
    assert "signal" in types


def test_execute_unified_exit_preserves_attribution_fields() -> None:
    candidate = ExitCandidate(
        candidate_type="runtime_close",
        layer="exit_management",
        bar_index=1,
        time_ms=300_000,
        reference_level="103",
        fill_price="103",
        reason="runtime_exit:market_close",
        rule_id="close",
        component_id="phase_runtime_exit",
        exit_kind="market_close",
    )
    result = arbitrate_unified_exit_candidates((candidate,))
    fill = execute_unified_exit(position(), result)
    assert fill is not None
    assert fill.layer == "exit_management"
    assert fill.rule_id == "close"
    assert fill.component_id == "phase_runtime_exit"
    assert fill.exit_kind == "market_close"
    assert fill.fill_price == Decimal("103")


def test_candidates_from_different_bars_are_rejected() -> None:
    one = ExitCandidate(
        candidate_type="signal",
        bar_index=1,
        time_ms=300_000,
        reference_level="100",
        fill_price="100",
        reason="signal",
    )
    two = one.model_copy(update={"bar_index": 2, "time_ms": 600_000})
    with pytest.raises(InvalidRequest, match="different bars"):
        arbitrate_unified_exit_candidates((one, two))
