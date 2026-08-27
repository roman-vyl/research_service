"""HTTP contracts for single-instance research backtests."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_service.accounting.contracts import AccountingPolicy
from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.application.backtests.from_deployable_instance import (
    build_backtest_request,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import DeployableStrategyInstance


class BacktestRunRequest(BaseModel):
    """Public `POST /api/research/backtests` request: a canonical deployable
    strategy instance (including `enabled`) plus Research-owned evaluation
    concerns. `enabled` is deployment metadata only — it crosses this HTTP
    boundary but is dropped, not evaluated, when projecting to the internal
    `SingleInstanceBacktestRequest` (`research-backtest-api-v1`, "Public
    request accepts a canonical deployable instance")."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: DeployableStrategyInstance
    range_policy: Literal["explicit_range", "full_available"] = "explicit_range"
    range: ExplicitRange | None = None
    execution: ExecutionPolicy = ExecutionPolicy()
    accounting: AccountingPolicy = AccountingPolicy()
    managed_policy_enabled: bool = True

    @model_validator(mode="after")
    def validate_range_shape(self) -> "BacktestRunRequest":
        # Mirrors SingleInstanceBacktestRequest.validate_range_shape so this
        # public request fails closed (422, via FastAPI's own body
        # validation) at the HTTP boundary itself, rather than surfacing a
        # bare pydantic ValidationError from inside to_application().
        if self.range_policy == "explicit_range" and self.range is None:
            raise ValueError("range_policy=explicit_range requires range.from_ms/to_ms")
        if self.range_policy == "full_available" and self.range is not None:
            raise ValueError("range_policy=full_available must not include a range")
        return self

    def to_application(self) -> SingleInstanceBacktestRequest:
        return build_backtest_request(
            self.strategy,
            range_policy=self.range_policy,
            range=self.range,
            execution=self.execution,
            accounting=self.accounting,
            managed_policy_enabled=self.managed_policy_enabled,
        )


class BacktestRunResponse(BaseModel):
    """Compact completion response; detailed data lives in the run artifact bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_backtest_api.v1"] = "research_backtest_api.v1"
    run_id: str = Field(min_length=1)
    status: Literal["completed"] = "completed"
    instance_id: str = Field(min_length=1)
    realised_trade_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0)
    final_equity: Decimal
    net_pnl: Decimal
    artifact_path: str = Field(min_length=1)
    manifest_contract_version: str = Field(min_length=1)
    market_data_hash: str | None = None
