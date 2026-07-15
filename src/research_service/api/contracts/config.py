"""Workbench config validation, serialization, and persistence contracts."""

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


class ConfigListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    path: str
    format: Literal["json", "yaml"]


class ConfigStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    selected_experiment_id: str | None = None
    selected_path: str | None = None
    draft: StrategyConfigDraft | None = None
    configs: list[ConfigListEntry] = Field(default_factory=list)


class SelectConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    experiment_id: str
