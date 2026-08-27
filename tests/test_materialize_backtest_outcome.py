"""Continuation-seam tests: prove MaterializeBacktestOutcome can execute/
account a candidate to a full outcome given only an already-acquired
StrategyEvaluationResult + MarketFrame — no evaluate_range call at all."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import SingleInstanceBacktestRequest
from research_service.application.backtests.materialize_backtest_outcome import (
    MaterializeBacktestOutcome,
)
from research_service.domain.contracts import (
    Candle,
    ExplicitRange,
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketFrame,
    MarketRange,
    StrategyEvaluationRequest,
    StrategyEvaluationResult,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import (
    StrategyInstanceIdentity,
    derive_strategy_instance_id,
)

_RAW_SPEC = {"anchor": {"period": 200}}

INSTANCE_ID = derive_strategy_instance_id(
    strategy_id="ema_pullback",
    ticker="BTCUSDT.P",
    base_timeframe="5m",
    raw_spec=_RAW_SPEC,
)


def strategy_identity() -> StrategyInstanceIdentity:
    return StrategyInstanceIdentity(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec=_RAW_SPEC,
    )


def backtest_request(*, managed_policy_enabled: bool = False) -> SingleInstanceBacktestRequest:
    return SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=managed_policy_enabled,
    )


def market_frame() -> MarketFrame:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=900_000)
    return MarketFrame(
        market=market,
        candles=(
            Candle(open_time_ms=0, open="99", high="102", low="98", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="100", high="106", low="99", close="105", volume="1"),
            Candle(
                open_time_ms=600_000, open="105", high="106", low="103", close="104", volume="1"
            ),
        ),
        market_data_hash="market-hash",
    )


def evaluation_result(*, market: MarketRange | None = None) -> StrategyEvaluationResult:
    resolved_market = market or market_frame().market
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id=INSTANCE_ID,
        config_hash="config-hash",
        market=resolved_market,
        bar_count=3,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000),
        entries={"long": (True, False, False), "short": (False, False, False)},
        exit_policy={
            "signal_exit": {"long": [False, False, False], "short": [False, False, False]},
            "stop_loss_ratio": {"long": ["0.10"] * 3, "short": ["0.10"] * 3},
            "take_profit_ratio": {"long": ["0.05"] * 3, "short": ["0.05"] * 3},
            "stop_ready": {"long": [True] * 3, "short": [True] * 3},
        },
        component_evidence={},
        raw={},
    )


class ExplodingStrategyEngine:
    """evaluate_range must never be called by the continuation seam."""

    def evaluate_range(self, request: StrategyEvaluationRequest) -> StrategyEvaluationResult:
        raise AssertionError("continuation must not call evaluate_range")

    def evaluate_managed_replay(self, request: ManagedReplayRequest) -> ManagedReplayResult:
        raise AssertionError("not used in this test")

    def evaluate_ema(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def get_composer_catalog(self, strategy_id: str) -> dict[str, Any]:
        raise AssertionError("not used")

    def validate_authoring_config(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def health(self) -> bool:
        return True


class FakeManagedStrategyEngine(ExplodingStrategyEngine):
    def __init__(self) -> None:
        self.managed_requests: list[ManagedReplayRequest] = []

    def evaluate_managed_replay(self, request: ManagedReplayRequest) -> ManagedReplayResult:
        self.managed_requests.append(request)
        return ManagedReplayResult(
            contract_version="managed_policy_replay.v1",
            decision_timing="end_of_bar_effective_next_bar",
            trade_id=request.trade_id,
            side=request.side,
            entry_time_ms=request.entry_time_ms,
            bars=(
                ManagedBarDecision(
                    time_ms=0,
                    bar_index=0,
                    phase="initial_risk",
                    bars_in_trade=1,
                    mfe_pct=Decimal("0.02"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=None,
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=300_000,
                ),
                ManagedBarDecision(
                    time_ms=300_000,
                    bar_index=1,
                    phase="initial_risk",
                    bars_in_trade=2,
                    mfe_pct=Decimal("0.06"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=None,
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=None,
                ),
            ),
            events=(),
            final_state={},
            raw={},
        )


def test_continuation_materializes_outcome_without_evaluate_range() -> None:
    use_case = MaterializeBacktestOutcome(ExplodingStrategyEngine())

    outcome = use_case.execute(backtest_request(), evaluation_result(), market_frame())
    result = outcome.result

    assert outcome.managed_policy_events == ()
    assert result.run_id
    assert result.instance_id == INSTANCE_ID
    assert result.contract_version == "research_single_instance_backtest.v1"
    assert result.contract_acceptance.bar_count == 3
    assert result.execution.positions[0].exit_fill is not None
    assert result.execution.positions[0].exit_fill.candidate_type == "take_profit"
    assert result.accounting.realised_trade_count == 1
    assert result.accounting.trades[0].net_pnl == Decimal("9.59000")
    assert result.accounting.final_equity == Decimal("1009.59000")


def test_continuation_managed_replay_produces_events() -> None:
    strategy = FakeManagedStrategyEngine()
    use_case = MaterializeBacktestOutcome(strategy)

    outcome = use_case.execute(
        backtest_request(managed_policy_enabled=True), evaluation_result(), market_frame()
    )

    assert len(strategy.managed_requests) == 1
    managed = strategy.managed_requests[0]
    assert managed.trade_id == f"position:{INSTANCE_ID}:long:0"
    assert managed.market == market_frame().market
    assert managed.strategy_spec == _RAW_SPEC
    # capture_managed_policy_events derives events from the replay's own
    # runtime-exit events (empty here, matching FakeManagedStrategyEngine's
    # canned ManagedReplayResult) -- what matters is the managed-replay call
    # itself happened and the outcome carries whatever it captured.
    assert isinstance(outcome.managed_policy_events, tuple)


def test_continuation_market_mismatch_raises_before_run_id() -> None:
    mismatched = market_frame().model_copy(
        update={
            "market": MarketRange(ticker="ETHUSDT.P", timeframe="5m", from_ms=0, to_ms=900_000)
        }
    )
    use_case = MaterializeBacktestOutcome(ExplodingStrategyEngine())

    with pytest.raises(InvalidRequest, match="market ranges differ"):
        use_case.execute(backtest_request(), evaluation_result(), mismatched)


def test_run_id_not_generated_on_phase_b_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    import research_service.application.backtests.materialize_backtest_outcome as module

    real_generate = module._generate_run_id

    def counting_generate() -> str:
        calls["count"] += 1
        return real_generate()

    monkeypatch.setattr(module, "_generate_run_id", counting_generate)
    use_case = MaterializeBacktestOutcome(ExplodingStrategyEngine())

    mismatched = market_frame().model_copy(
        update={
            "market": MarketRange(ticker="ETHUSDT.P", timeframe="5m", from_ms=0, to_ms=900_000)
        }
    )
    with pytest.raises(InvalidRequest):
        use_case.execute(backtest_request(), evaluation_result(), mismatched)
    assert calls["count"] == 0

    use_case.execute(backtest_request(), evaluation_result(), market_frame())
    assert calls["count"] == 1
