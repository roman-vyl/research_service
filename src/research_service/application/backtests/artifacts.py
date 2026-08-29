"""Shared run-artifact manifest models (I8, `compact-strategy-evaluation-
boundary-v1`: the batch-only writer this module used to also define,
`PersistSingleInstanceBacktest`, is deleted -- both single-instance and
batch persistence now go through `PersistSingleInstanceRun`,
`application/backtests/persist_run.py`)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RunArtifactFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class RunArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_run_artifacts.v1"] = "research_run_artifacts.v1"
    run_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    created_at_utc: str = Field(min_length=1)
    backtest_contract_version: str = Field(min_length=1)
    strategy_contract_version: str = Field(min_length=1)
    execution_contract_version: str = Field(min_length=1)
    accounting_contract_version: str = Field(min_length=1)
    market_data_hash: str | None = None
    files: tuple[RunArtifactFile, ...]


class PersistedRunArtifacts(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    manifest: RunArtifactManifest
