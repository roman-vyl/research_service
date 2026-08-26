"""Workbench strategy-config draft contracts shared by API, application, and adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    init_cash: float | None = None
    fees: float | None = None
    slippage: float | None = None


class StrategyConfigDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_version: int = 1
    experiment_id: str
    family: str
    execution: ExecutionDraft
    instances: list[dict[str, Any]] = Field(min_length=1)


class ConfigListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    path: str
    format: Literal["json", "yaml"]
