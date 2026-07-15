"""Single-instance backtest application contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_service.accounting.contracts import AccountingPolicy, TradeAccountingResult
from research_service.domain.contracts import StrategyEvaluationRequest, StrategyEvaluationResult
from research_service.domain.execution import ExecutionLoopResult, ExecutionPolicy
from research_service.application.backtests.strategy_contract import (
    StrategyExecutionContractAcceptance,
)


class SingleInstanceBacktestRequest(BaseModel):
    """One authoritative research run for one strategy instance and market range."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    strategy: StrategyEvaluationRequest
    execution: ExecutionPolicy = ExecutionPolicy()
    accounting: AccountingPolicy = AccountingPolicy()
    managed_policy_enabled: bool = True
    range_policy: Literal["explicit_range", "full_available"] = "explicit_range"


class SingleInstanceBacktestResult(BaseModel):
    """Immutable result assembled from strategy, execution and accounting facts."""

    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_single_instance_backtest.v1"] = (
        "research_single_instance_backtest.v1"
    )
    run_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    strategy_evaluation: StrategyEvaluationResult
    contract_acceptance: StrategyExecutionContractAcceptance
    execution: ExecutionLoopResult
    accounting: TradeAccountingResult

    @model_validator(mode="after")
    def validate_identity(self) -> "SingleInstanceBacktestResult":
        if self.instance_id != self.strategy_evaluation.instance_id:
            raise ValueError("backtest instance differs from strategy evaluation")
        if self.instance_id != self.execution.instance_id:
            raise ValueError("backtest instance differs from execution result")
        if self.instance_id != self.accounting.instance_id:
            raise ValueError("backtest instance differs from accounting result")
        if self.strategy_evaluation.market != self.execution.market:
            raise ValueError("strategy and execution markets differ")
        return self
