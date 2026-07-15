"""Sequential batch experiment contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_service.application.backtests.contracts import SingleInstanceBacktestRequest


class BatchCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    backtest: SingleInstanceBacktestRequest
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    candidates: tuple[BatchCandidateRequest, ...] = Field(min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def validate_unique_identity(self) -> "BatchExperimentRequest":
        candidate_ids = [item.candidate_id for item in self.candidates]
        run_ids = [item.backtest.run_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique within a batch")
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("run_id values must be unique within a batch")
        return self


class BatchCandidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    run_id: str
    instance_id: str
    status: Literal["completed", "failed"]
    artifact_path: str | None = None
    realised_trade_count: int | None = Field(default=None, ge=0)
    open_position_count: int | None = Field(default=None, ge=0)
    final_equity: Decimal | None = None
    gross_pnl: Decimal | None = None
    fees_paid: Decimal | None = None
    net_pnl: Decimal | None = None
    market_data_hash: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_batch_experiment.v1"] = "research_batch_experiment.v1"
    experiment_id: str
    status: Literal["completed", "completed_with_failures"]
    candidate_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    candidates: tuple[BatchCandidateResult, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "BatchExperimentResult":
        if self.candidate_count != len(self.candidates):
            raise ValueError("candidate_count differs from candidates")
        completed = sum(item.status == "completed" for item in self.candidates)
        failed = sum(item.status == "failed" for item in self.candidates)
        if self.completed_count != completed or self.failed_count != failed:
            raise ValueError("batch status counts differ from candidates")
        expected = "completed" if failed == 0 else "completed_with_failures"
        if self.status != expected:
            raise ValueError("batch status differs from failure count")
        return self


class PersistedBatchArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    artifact_path: str
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
