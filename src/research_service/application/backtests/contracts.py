"""Single-instance backtest application contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from research_service.accounting.contracts import AccountingPolicy
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import StrategyInstanceIdentity


class SingleInstanceBacktestRequest(BaseModel):
    """One authoritative research run for one strategy instance and market range.

    `run_id` is Research-generated, not a request field (see
    `research-backtest-api-v1`'s "Server-generated run identity"). `strategy`
    is the canonical strategy-instance identity subset only — no `enabled`,
    no `instance_id`, no `family`/`variant`/`strategy_version`. The range
    portion is conditional on `range_policy`: `explicit_range` requires a
    real `range`; `full_available` must not include one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: StrategyInstanceIdentity
    range_policy: Literal["explicit_range", "full_available"] = "explicit_range"
    range: ExplicitRange | None = None
    execution: ExecutionPolicy = ExecutionPolicy()
    accounting: AccountingPolicy = AccountingPolicy()
    managed_policy_enabled: bool = True

    @model_validator(mode="after")
    def validate_range_shape(self) -> "SingleInstanceBacktestRequest":
        if self.range_policy == "explicit_range" and self.range is None:
            raise ValueError("range_policy=explicit_range requires range.from_ms/to_ms")
        if self.range_policy == "full_available" and self.range is not None:
            raise ValueError("range_policy=full_available must not include a range")
        return self
