"""HTTP contracts for immutable research run artifacts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.application.backtests.artifacts import RunArtifactManifest
from research_service.application.backtests.contracts import SingleInstanceBacktestResult
from research_service.accounting.contracts import TradeRecord


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_summary.v1"] = "research_run_summary.v1"
    run_id: str = Field(min_length=1)
    created_at_utc: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
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


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_run_detail.v1"] = "research_run_detail.v1"
    manifest: RunArtifactManifest
    result: SingleInstanceBacktestResult


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
