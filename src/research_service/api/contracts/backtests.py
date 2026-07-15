"""HTTP contracts for single-instance research backtests."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BacktestRunResponse(BaseModel):
    """Compact completion response; detailed data lives in the run artifact bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_backtest_api.v1"] = "research_backtest_api.v1"
    run_id: str = Field(min_length=1)
    status: Literal["completed"] = "completed"
    instance_id: str = Field(min_length=1)
    realised_trade_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0)
    final_equity: Decimal
    net_pnl: Decimal
    artifact_path: str = Field(min_length=1)
    manifest_contract_version: str = Field(min_length=1)
    market_data_hash: str | None = None
