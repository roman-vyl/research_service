"""Project a stored `DeployableStrategyInstance` into a backtest request.

This is a projection of the one canonical strategy representation into a
narrower evaluation request — never a translator between two different
strategy representations (canonical-strategy-instance-v1, Decision 8).
`enabled` is dropped here (via `DeployableStrategyInstance.identity()`);
everything else is Research-owned evaluation concerns layered on top.
"""

from __future__ import annotations

from research_service.accounting.contracts import AccountingPolicy
from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import DeployableStrategyInstance


def build_backtest_request(
    instance: DeployableStrategyInstance,
    *,
    range_policy: str = "explicit_range",
    range: ExplicitRange | None = None,
    execution: ExecutionPolicy | None = None,
    accounting: AccountingPolicy | None = None,
    managed_policy_enabled: bool = True,
) -> SingleInstanceBacktestRequest:
    return SingleInstanceBacktestRequest(
        strategy=instance.identity(),
        range_policy=range_policy,  # type: ignore[arg-type]
        range=range,
        execution=execution or ExecutionPolicy(),
        accounting=accounting or AccountingPolicy(),
        managed_policy_enabled=managed_policy_enabled,
    )
