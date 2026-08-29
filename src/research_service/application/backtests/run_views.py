"""HTTP contracts for immutable research run artifacts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.application.backtests.artifacts import RunArtifactManifest
from research_service.domain.contracts import HistoricalExecutionProjectionDTO
from research_service.domain.execution import ExecutionEvent
from research_service.accounting.contracts import TradeRecord


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_summary.v1"] = "research_run_summary.v1"
    run_id: str = Field(min_length=1)
    created_at_utc: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)
    realised_trade_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0)
    final_equity: Decimal
    net_pnl: Decimal
    market_data_hash: str | None = None


class RunCompactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_compact_summary.v1"] = "research_run_compact_summary.v1"
    summary: RunSummary
    gross_pnl: Decimal
    fees_paid: Decimal
    artifact_contract_version: str = Field(min_length=1)


class RunDetailResult(BaseModel):
    """The canonical (I7, `compact-strategy-evaluation-boundary-v1`)
    resolved result content for `RunDetail` -- assembled by
    `ReadResearchRuns` from the canonical `result.json`'s references plus
    the referenced files, not a re-embedded on-disk shape itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_single_instance_run.v2"] = (
        "research_single_instance_run.v2"
    )
    run_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    strategy_evaluation: HistoricalExecutionProjectionDTO
    execution_events: tuple[ExecutionEvent, ...]
    trades: tuple[TradeRecord, ...]


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_detail.v1"] = "research_run_detail.v1"
    manifest: RunArtifactManifest
    result: RunDetailResult
    # Sourced from the persisted request.json (request.strategy.strategy_spec) —
    # the authoritative strategy spec for one run. Only this field is surfaced;
    # the rest of the persisted request envelope (execution/accounting policy,
    # range_policy, etc.) is deliberately not exposed.
    strategy_spec: dict[str, Any]


class RunTrades(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_trades.v1"] = "research_run_trades.v1"
    run_id: str = Field(min_length=1)
    trades: tuple[TradeRecord, ...]


class RunMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_metrics.v1"] = "research_run_metrics.v1"
    run_id: str = Field(min_length=1)
    initial_equity: Decimal
    final_equity: Decimal
    realised_trade_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0)
    gross_pnl: Decimal
    fees_paid: Decimal
    net_pnl: Decimal
