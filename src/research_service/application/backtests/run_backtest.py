"""Authoritative single-instance backtest orchestration."""

from __future__ import annotations

from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.application.backtests.history_window import ResolveBacktestWindow
from research_service.application.backtests.materialize_backtest_outcome import (
    MaterializeBacktestOutcome,
    SingleInstanceBacktestOutcome,
)
from research_service.domain.contracts import StrategyEvaluationRequest
from research_service.domain.strategy_instance import derive_strategy_instance_id
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import StrategyEnginePort

__all__ = ["RunSingleInstanceBacktest", "SingleInstanceBacktestOutcome"]


class RunSingleInstanceBacktest:
    """Resolve the market window, acquire one Strategy Engine evaluation, and
    delegate the rest (execution/managed-replay/accounting/result
    construction) to `MaterializeBacktestOutcome` — the Phase-B continuation
    seam that a future batch path can call directly with an
    Engine-evaluation-per-candidate it already has in hand."""

    def __init__(
        self,
        strategy_engine: StrategyEnginePort,
        market_data: MarketDataPort,
    ) -> None:
        self._strategy_engine = strategy_engine
        self._market_data = market_data
        self._window_planner = ResolveBacktestWindow(market_data)
        self._materialize = MaterializeBacktestOutcome(strategy_engine)

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
    ) -> SingleInstanceBacktestOutcome:
        instance_id = derive_strategy_instance_id(
            strategy_id=request.strategy.strategy_id,
            ticker=request.strategy.ticker,
            base_timeframe=request.strategy.base_timeframe,
            raw_spec=request.strategy.raw_spec,
        )

        window = self._window_planner.execute(
            ticker=request.strategy.ticker,
            timeframe=request.strategy.base_timeframe,
            explicit_range=request.range,
            range_policy=request.range_policy,
        )
        strategy_request = StrategyEvaluationRequest(
            strategy_id=request.strategy.strategy_id,
            instance_id=instance_id,
            strategy_spec=request.strategy.raw_spec,
            market=window.market,
            expected_market_data_hash=window.market_data_hash,
        )
        evaluation = self._strategy_engine.evaluate_range(strategy_request)
        market_frame = self._market_data.read_historical_range(
            window.market,
            expected_market_data_hash=window.market_data_hash,
        )

        return self._materialize.execute(request, evaluation, market_frame)
