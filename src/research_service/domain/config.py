"""Workbench strategy-config draft contracts shared by API, application, and adapters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.strategy_instance import DeployableStrategyInstance


class ExecutionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    init_cash: float | None = None
    fees: float | None = None
    slippage: float | None = None


class StrategyConfigDraft(BaseModel):
    """A Research grouping/experiment envelope over canonical strategy
    instances. `experiment_id` is grouping identity, not strategy identity
    (canonical-strategy-instance-v1) — each `instances` entry is a full
    `DeployableStrategyInstance`, not an untyped per-instance shape."""

    model_config = ConfigDict(extra="forbid")

    config_version: int = 1
    experiment_id: str
    strategy_id: str
    execution: ExecutionDraft
    instances: list[DeployableStrategyInstance] = Field(min_length=1)


class ConfigListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    path: str
    format: Literal["json", "yaml"]
