"""Batch experiment contracts.

An experiment compares several configurations of ONE strategy over ONE
ticker/base_timeframe/historical comparison window -- not an array of
independent standalone backtest requests. `range`/`range_policy` live at
the experiment level, once, shared by every candidate; each candidate
contributes only what legitimately varies between comparable
configurations (`raw_spec`, execution/accounting policy,
managed_policy_enabled, metadata).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_service.accounting.contracts import AccountingPolicy
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import DeployableStrategyInstance

_CANDIDATE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class BatchCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, pattern=_CANDIDATE_ID_PATTERN)
    strategy: DeployableStrategyInstance
    execution: ExecutionPolicy = ExecutionPolicy()
    accounting: AccountingPolicy = AccountingPolicy()
    managed_policy_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchExperimentRequest(BaseModel):
    """One experiment: one strategy_id, one ticker, one base_timeframe, one
    comparison window, shared by every candidate -- never a per-candidate
    concern (`research-batch-experiments-v1`, "Experiment owns one range
    policy/window")."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    strategy_id: str = Field(min_length=1)
    range_policy: Literal["explicit_range", "full_available"] = "explicit_range"
    range: ExplicitRange | None = None
    candidates: tuple[BatchCandidateRequest, ...] = Field(min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def validate_experiment_invariants(self) -> "BatchExperimentRequest":
        if self.range_policy == "explicit_range" and self.range is None:
            raise ValueError("range_policy=explicit_range requires range.from_ms/to_ms")
        if self.range_policy == "full_available" and self.range is not None:
            raise ValueError("range_policy=full_available must not include a range")

        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique within a batch")

        # One experiment compares configurations of one strategy over one
        # ticker/base_timeframe -- candidates never get their own comparison
        # universe (research-batch-experiments-v1, "Experiment owns one
        # range policy/window").
        for index, candidate in enumerate(self.candidates):
            if candidate.strategy.strategy_id != self.strategy_id:
                raise ValueError(
                    f"candidates[{index}].strategy.strategy_id must match "
                    f"experiment strategy_id {self.strategy_id!r}; "
                    f"got {candidate.strategy.strategy_id!r}"
                )
        tickers = {item.strategy.ticker for item in self.candidates}
        if len(tickers) > 1:
            raise ValueError("every candidate must share the same strategy.ticker")
        base_timeframes = {item.strategy.base_timeframe for item in self.candidates}
        if len(base_timeframes) > 1:
            raise ValueError("every candidate must share the same strategy.base_timeframe")
        return self


class BatchCandidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    # Present only when status == "completed" — a failed candidate never
    # had a run created, so it never got a generated run_id
    # (research-batch-experiments-v1, "Run identity generated only on
    # success"). instance_id, unlike run_id, is a pure function of the
    # candidate's identity subset and is always known, even on failure.
    run_id: str | None = None
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
