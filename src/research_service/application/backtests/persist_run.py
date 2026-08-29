"""Persist a run in the canonical I6.D shape (I7, `compact-strategy-
evaluation-boundary-v1`) -- both `RunSingleInstanceBacktest` and
`RunBatchExperiment` use this writer since I8 (the batch-only legacy
`PersistSingleInstanceBacktest` was deleted). `strategy_evaluation.json`
IS the real `HistoricalExecutionProjection`; `result.json` references it
(and `trades.json`/`execution_events.json`) by sha256 identity, never
re-embedding, plus a lightweight market-identity/provenance subset so
identity-only consumers don't need to open a second file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.accounting.contracts import TradeAccountingResult
from research_service.application.backtests.artifacts import (
    PersistedRunArtifacts,
    RunArtifactFile,
    RunArtifactManifest,
)
from research_service.application.backtests.contracts import SingleInstanceBacktestRequest
from research_service.domain.contracts import HistoricalExecutionProjectionDTO
from research_service.domain.execution import ExecutionLoopResult
from research_service.domain.strategy_instance import derive_strategy_instance_id
from research_service.execution.managed_policy_events import (
    ManagedPolicyEvent,
    ManagedPolicyEventTrace,
)
from research_service.ports.artifacts import RunArtifactStore

_RESULT_CONTRACT_VERSION: Literal["research_single_instance_run.v2"] = (
    "research_single_instance_run.v2"
)


class ArtifactRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SingleInstanceRunResult(BaseModel):
    """Canonical on-disk `result.json` shape (I6.D): identity subset plus
    references by sha256 -- never a re-embedded copy of
    `strategy_evaluation.json`/`trades.json`/`execution_events.json`.
    This is the only `result.json` shape `ReadResearchRuns` recognizes
    after I7 -- no `contract_version`-based branching, no legacy shape
    support (`research-production-cutover-v1`)."""

    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_single_instance_run.v2"] = _RESULT_CONTRACT_VERSION
    run_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)
    bar_count: int = Field(ge=0)
    market_data_hash: str = Field(min_length=1)
    strategy_evaluation_ref: ArtifactRef
    trades_ref: ArtifactRef
    execution_events_ref: ArtifactRef


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


class PersistSingleInstanceRun:
    """Persist one completed single-instance run as an immutable atomic run
    directory, in the canonical I6.D shape."""

    def __init__(self, store: RunArtifactStore) -> None:
        self._store = store

    def execute(
        self,
        request: SingleInstanceBacktestRequest,
        *,
        run_id: str,
        instance_id: str,
        strategy_evaluation: HistoricalExecutionProjectionDTO,
        execution: ExecutionLoopResult,
        accounting: TradeAccountingResult,
        managed_policy_events: tuple[ManagedPolicyEvent, ...] = (),
    ) -> PersistedRunArtifacts:
        expected_instance_id = derive_strategy_instance_id(
            strategy_id=request.strategy.strategy_id,
            ticker=request.strategy.ticker,
            base_timeframe=request.strategy.base_timeframe,
            raw_spec=request.strategy.raw_spec,
        )
        if expected_instance_id != instance_id:
            raise ValueError("result instance_id does not match request identity subset")

        strategy_evaluation_bytes = _model_json_bytes(strategy_evaluation)
        trades_bytes = _json_bytes([item.model_dump(mode="json") for item in accounting.trades])
        execution_events_bytes = _json_bytes(
            [item.model_dump(mode="json") for item in execution.events]
        )
        metrics_bytes = _json_bytes(
            {
                "initial_equity": str(accounting.initial_equity),
                "final_equity": str(accounting.final_equity),
                "realised_trade_count": accounting.realised_trade_count,
                "open_position_count": accounting.open_position_count,
                "gross_pnl": str(accounting.gross_pnl),
                "fees_paid": str(accounting.fees_paid),
                "net_pnl": str(accounting.net_pnl),
            }
        )
        managed_policy_events_bytes = _model_json_bytes(
            ManagedPolicyEventTrace(run_id=run_id, events=managed_policy_events)
        )
        request_bytes = _model_json_bytes(request)

        strategy_evaluation_record = _file_record(
            "strategy_evaluation.json", strategy_evaluation_bytes
        )
        trades_record = _file_record("trades.json", trades_bytes)
        execution_events_record = _file_record("execution_events.json", execution_events_bytes)

        result = SingleInstanceRunResult(
            run_id=run_id,
            instance_id=instance_id,
            config_hash=strategy_evaluation.config_hash,
            ticker=strategy_evaluation.market.ticker,
            timeframe=strategy_evaluation.market.timeframe,
            from_ms=strategy_evaluation.market.from_ms,
            to_ms=strategy_evaluation.market.to_ms,
            bar_count=strategy_evaluation.bar_count,
            market_data_hash=strategy_evaluation.market_data_hash,
            strategy_evaluation_ref=ArtifactRef(
                path="strategy_evaluation.json", sha256=strategy_evaluation_record.sha256
            ),
            trades_ref=ArtifactRef(path="trades.json", sha256=trades_record.sha256),
            execution_events_ref=ArtifactRef(
                path="execution_events.json", sha256=execution_events_record.sha256
            ),
        )
        result_bytes = _model_json_bytes(result)

        payloads: dict[str, bytes] = {
            "request.json": request_bytes,
            "strategy_evaluation.json": strategy_evaluation_bytes,
            "execution_events.json": execution_events_bytes,
            "trades.json": trades_bytes,
            "metrics.json": metrics_bytes,
            "managed_policy_events.json": managed_policy_events_bytes,
            "result.json": result_bytes,
        }
        records = tuple(_file_record(path, payload) for path, payload in sorted(payloads.items()))
        manifest = RunArtifactManifest(
            run_id=run_id,
            instance_id=instance_id,
            created_at_utc=datetime.now(UTC).isoformat(),
            backtest_contract_version=result.contract_version,
            strategy_contract_version=strategy_evaluation.contract_version,
            execution_contract_version=execution.contract_version,
            accounting_contract_version=accounting.contract_version,
            market_data_hash=strategy_evaluation.market_data_hash,
            files=records,
        )
        payloads["manifest.json"] = _model_json_bytes(manifest)
        destination = self._store.write_run_bundle(run_id, payloads)
        return PersistedRunArtifacts(
            run_id=run_id,
            artifact_path=str(destination),
            manifest=manifest,
        )
