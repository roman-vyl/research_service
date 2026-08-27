"""Versioned serialization and persistence of completed research runs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.application.backtests.contracts import (
    SingleInstanceBacktestRequest,
    SingleInstanceBacktestResult,
)
from research_service.domain.strategy_instance import derive_strategy_instance_id
from research_service.execution.managed_policy_events import (
    ManagedPolicyEvent,
    ManagedPolicyEventTrace,
)
from research_service.ports.artifacts import RunArtifactStore


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


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _model_json_bytes(model: BaseModel) -> bytes:
    return _json_bytes(model.model_dump(mode="json"))


def _file_record(path: str, payload: bytes) -> RunArtifactFile:
    return RunArtifactFile(
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


class PersistSingleInstanceBacktest:
    """Persist one completed backtest as an immutable atomic run directory."""

    def __init__(self, store: RunArtifactStore) -> None:
        self._store = store

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
        result: SingleInstanceBacktestResult,
        managed_policy_events: tuple[ManagedPolicyEvent, ...] = (),
    ) -> PersistedRunArtifacts:
        # run_id is Research-generated (no longer a request field) — nothing
        # to cross-check it against. instance_id, however, is still an
        # invariant worth defending: it must be exactly what derives from
        # the request's own identity subset.
        expected_instance_id = derive_strategy_instance_id(
            strategy_id=request.strategy.strategy_id,
            ticker=request.strategy.ticker,
            base_timeframe=request.strategy.base_timeframe,
            raw_spec=request.strategy.raw_spec,
        )
        if expected_instance_id != result.instance_id:
            raise ValueError("result instance_id does not match request identity subset")

        payloads: dict[str, bytes] = {
            "request.json": _model_json_bytes(request),
            "strategy_evaluation.json": _model_json_bytes(result.strategy_evaluation),
            "execution_events.json": _json_bytes(
                [item.model_dump(mode="json") for item in result.execution.events]
            ),
            "trades.json": _json_bytes(
                [item.model_dump(mode="json") for item in result.accounting.trades]
            ),
            "metrics.json": _json_bytes(
                {
                    "initial_equity": str(result.accounting.initial_equity),
                    "final_equity": str(result.accounting.final_equity),
                    "realised_trade_count": result.accounting.realised_trade_count,
                    "open_position_count": result.accounting.open_position_count,
                    "gross_pnl": str(result.accounting.gross_pnl),
                    "fees_paid": str(result.accounting.fees_paid),
                    "net_pnl": str(result.accounting.net_pnl),
                }
            ),
            # Always written, even when empty (no managed policy, or no rules
            # fired) — an empty trace is a valid outcome, not an omission.
            "managed_policy_events.json": _model_json_bytes(
                ManagedPolicyEventTrace(run_id=result.run_id, events=managed_policy_events)
            ),
            "result.json": _model_json_bytes(result),
        }
        records = tuple(_file_record(path, payload) for path, payload in sorted(payloads.items()))
        manifest = RunArtifactManifest(
            run_id=result.run_id,
            instance_id=result.instance_id,
            created_at_utc=datetime.now(UTC).isoformat(),
            backtest_contract_version=result.contract_version,
            strategy_contract_version=result.strategy_evaluation.contract_version,
            execution_contract_version=result.execution.contract_version,
            accounting_contract_version=result.accounting.contract_version,
            market_data_hash=result.strategy_evaluation.market_data_hash,
            files=records,
        )
        payloads["manifest.json"] = _model_json_bytes(manifest)
        destination = self._store.write_run_bundle(result.run_id, payloads)
        return PersistedRunArtifacts(
            run_id=result.run_id,
            artifact_path=str(destination),
            manifest=manifest,
        )
