"""Workbench config validation, serialization, and persistence contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.config import ConfigListEntry, ExecutionDraft, StrategyConfigDraft

__all__ = [
    "ConfigListEntry",
    "ConfigStateResponse",
    "ExecutionDraft",
    "SaveConfigRequest",
    "SaveConfigResult",
    "SelectConfigRequest",
    "SerializeResult",
    "StrategyConfigDraft",
    "ValidationErrorItem",
    "ValidationResult",
]


class ValidationErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    message: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)


class SerializeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    format: Literal["json", "yaml"]
    content: str = ""
    errors: list[ValidationErrorItem] = Field(default_factory=list)


class SaveConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: StrategyConfigDraft


class SaveConfigResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    path: str | None = None
    errors: list[ValidationErrorItem] = Field(default_factory=list)


class ConfigStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    selected_experiment_id: str | None = None
    selected_path: str | None = None
    draft: StrategyConfigDraft | None = None
    configs: list[ConfigListEntry] = Field(default_factory=list)


class SelectConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    experiment_id: str
