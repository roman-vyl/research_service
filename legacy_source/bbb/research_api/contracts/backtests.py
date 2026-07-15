"""Backtest run contracts — sync POST from Workbench."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_api.contracts.config import StrategyConfigDraft, ValidationErrorItem


class RunBacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: StrategyConfigDraft | None = None
    """Validated and saved before run when provided."""

    config_path: str | None = None
    """Repo-relative path under ``research/experiments/configs/`` (after save or explicit)."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> RunBacktestRequest:
        has_draft = self.draft is not None
        has_path = self.config_path is not None
        if has_draft and has_path:
            raise ValueError("provide exactly one of draft or config_path, not both")
        if not has_draft and not has_path:
            raise ValueError("provide exactly one of draft or config_path")
        return self


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    run_id: str | None = None
    config_path: str | None = None
    errors: list[ValidationErrorItem] = Field(default_factory=list)
