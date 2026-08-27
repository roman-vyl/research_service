from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import (
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (
    Candle,
    ContinuityAudit,
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketFrame,
    MarketRange,
    StrategyEvaluationRequest,
    StrategyEvaluationResult,
    StreamBounds,
)
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExecutionPolicy


def market_frame() -> MarketFrame:
    market = MarketRange(
        ticker="BTCUSDT.P",
        timeframe="5m",
        from_ms=0,
        to_ms=900_000,
    )
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


def strategy_request() -> StrategyEvaluationRequest:
    return StrategyEvaluationRequest(
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="instance-1",
        strategy_spec={"anchor": {"period": 200}},
        market=market_frame().market,
    )


def strategy_result(*, market: MarketRange | None = None) -> StrategyEvaluationResult:
    resolved_market = market or market_frame().market
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        strategy_version="v1",
        instance_id="instance-1",
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


class FakeStrategyEngine:
    def __init__(self, result: StrategyEvaluationResult) -> None:
        self.result = result
        self.range_requests: list[StrategyEvaluationRequest] = []
        self.managed_requests: list[ManagedReplayRequest] = []

    def evaluate_range(self, request: StrategyEvaluationRequest) -> StrategyEvaluationResult:
        self.range_requests.append(request)
        return self.result

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

    def evaluate_ema(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def get_composer_catalog(self, strategy_id: str) -> dict[str, Any]:
        raise AssertionError("not used")

    def validate_authoring_config(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def health(self) -> bool:
        return True


class FakeMarketData:
    def __init__(self, frame: MarketFrame) -> None:
        self.frame = frame
        self.requests: list[MarketRange] = []

    def get_bounds(self, *, ticker: str, timeframe: str) -> StreamBounds:
        return StreamBounds(
            ticker=ticker,
            timeframe=timeframe,
            earliest_open_time_ms=self.frame.market.from_ms,
            latest_open_time_ms=self.frame.market.to_ms - self.frame.market.step_ms,
            stream_state="ready",
        )

    def audit_range(self, market: MarketRange) -> ContinuityAudit:
        return ContinuityAudit(
            market=market,
            candle_count=len(self.frame.candles),
            is_continuous=True,
            stream_state="ready",
            market_data_hash="market-hash",
        )

    def read_historical_range(
        self,
        market: MarketRange,
        *,
        expected_market_data_hash: str,
    ) -> MarketFrame:
        assert expected_market_data_hash == "market-hash"
        self.requests.append(market)
        return self.frame

    def read_range(self, market: MarketRange) -> MarketFrame:
        self.requests.append(market)
        return self.frame

    def health(self) -> bool:
        return True


def test_single_instance_backtest_composes_all_layers() -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case = RunSingleInstanceBacktest(strategy, market)

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            run_id="run-1",
            strategy=strategy_request(),
            execution=ExecutionPolicy(quantity=Decimal("2")),
            accounting=AccountingPolicy(
                initial_equity=Decimal("1000"),
                entry_fee_rate=Decimal("0.001"),
                exit_fee_rate=Decimal("0.001"),
            ),
            managed_policy_enabled=False,
        )
    )
    result = outcome.result
    assert outcome.managed_policy_events == ()

    assert result.contract_version == "research_single_instance_backtest.v1"
    assert strategy.range_requests == [
        strategy_request().model_copy(update={"expected_market_data_hash": "market-hash"})
    ]
    assert market.requests == [strategy_request().market]
    assert result.contract_acceptance.bar_count == 3
    assert result.execution.positions[0].exit_fill is not None
    assert result.execution.positions[0].exit_fill.candidate_type == "take_profit"
    assert result.accounting.realised_trade_count == 1
    assert result.accounting.trades[0].net_pnl == Decimal("9.59000")
    assert result.accounting.final_equity == Decimal("1009.59000")
    assert strategy.managed_requests == []


def test_managed_replay_request_uses_reference_entry_price() -> None:
    strategy = FakeStrategyEngine(strategy_result())
    use_case = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame()))

    use_case.execute(
        SingleInstanceBacktestRequest(
            run_id="run-managed",
            strategy=strategy_request(),
            execution=ExecutionPolicy(entry_slippage_rate=Decimal("0.01")),
        )
    )

    assert len(strategy.managed_requests) == 1
    managed = strategy.managed_requests[0]
    assert managed.trade_id == "position:instance-1:long:0"
    assert managed.entry_time_ms == 0
    assert managed.entry_price == Decimal("100")
    assert managed.strategy_spec == strategy_request().strategy_spec


def test_market_mismatch_stops_before_execution() -> None:
    mismatched = market_frame().model_copy(
        update={
            "market": MarketRange(
                ticker="ETHUSDT.P",
                timeframe="5m",
                from_ms=0,
                to_ms=900_000,
            )
        }
    )
    use_case = RunSingleInstanceBacktest(
        FakeStrategyEngine(strategy_result()),
        FakeMarketData(mismatched),
    )

    with pytest.raises(InvalidRequest, match="market ranges differ"):
        use_case.execute(
            SingleInstanceBacktestRequest(
                run_id="run-bad-market",
                strategy=strategy_request(),
                managed_policy_enabled=False,
            )
        )


def test_full_available_resolved_market_reaches_every_downstream_stage() -> None:
    resolved_market = market_frame().market
    narrow_requested_market = resolved_market.model_copy(
        update={"from_ms": 300_000, "to_ms": 600_000}
    )
    narrow_request = strategy_request().model_copy(
        update={"market": narrow_requested_market}
    )
    strategy = FakeStrategyEngine(strategy_result(market=resolved_market))
    market = FakeMarketData(market_frame())
    use_case = RunSingleInstanceBacktest(strategy, market)

    use_case.execute(
        SingleInstanceBacktestRequest(
            run_id="run-full-available",
            strategy=narrow_request,
            range_policy="full_available",
            execution=ExecutionPolicy(entry_slippage_rate=Decimal("0.01")),
            managed_policy_enabled=True,
        )
    )

    assert narrow_requested_market != resolved_market
    assert strategy.range_requests[0].market == resolved_market
    assert market.requests == [resolved_market]
    assert len(strategy.managed_requests) == 1
    assert strategy.managed_requests[0].market == resolved_market
