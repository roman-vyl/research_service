"""Read immutable run bundles and project BFF run/result contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from research_service.application.backtests.run_views import (
    RunCompactSummary,
    RunDetail,
    RunMetrics,
    RunSummary,
    RunTrades,
)
from research_service.application.backtests.artifacts import RunArtifactManifest
from research_service.application.backtests.contracts import (
    SingleInstanceBacktestRequest,
    SingleInstanceBacktestResult,
)
from research_service.domain.errors import InvalidRunArtifact, RunNotFound
from research_service.ports.artifacts import RunArtifactReader


@dataclass(frozen=True, slots=True)
class _RunDocuments:
    manifest: RunArtifactManifest
    request: SingleInstanceBacktestRequest
    result: SingleInstanceBacktestResult
    metrics: dict[str, Any]


def _decimal(metrics: dict[str, Any], key: str) -> Decimal:
    try:
        return Decimal(str(metrics[key]))
    except (KeyError, ValueError) as exc:
        raise InvalidRunArtifact(f"metrics.json has invalid {key}") from exc


def _int(metrics: dict[str, Any], key: str) -> int:
    try:
        return int(metrics[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidRunArtifact(f"metrics.json has invalid {key}") from exc


class ReadResearchRuns:
    """Read only the new versioned artifact-store layout."""

    def __init__(self, store: RunArtifactReader) -> None:
        self._store = store

    def list_runs(self) -> tuple[RunSummary, ...]:
        summaries = [
            self._summary(self._documents(run_id)) for run_id in self._store.list_run_ids()
        ]
        summaries.sort(key=lambda item: item.created_at_utc, reverse=True)
        return tuple(summaries)

    def latest(self) -> RunDetail:
        summaries = self.list_runs()
        if not summaries:
            raise RunNotFound("latest")
        return self.detail(summaries[0].run_id)

    def detail(self, run_id: str) -> RunDetail:
        documents = self._documents(run_id)
        return RunDetail(manifest=documents.manifest, result=documents.result)

    def compact_summary(self, run_id: str) -> RunCompactSummary:
        documents = self._documents(run_id)
        return RunCompactSummary(
            summary=self._summary(documents),
            gross_pnl=_decimal(documents.metrics, "gross_pnl"),
            fees_paid=_decimal(documents.metrics, "fees_paid"),
            artifact_contract_version=documents.manifest.contract_version,
        )

    def trades(self, run_id: str) -> RunTrades:
        documents = self._documents(run_id)
        return RunTrades(run_id=run_id, trades=documents.result.accounting.trades)

    def metrics(self, run_id: str) -> RunMetrics:
        documents = self._documents(run_id)
        return RunMetrics(
            run_id=run_id,
            initial_equity=_decimal(documents.metrics, "initial_equity"),
            final_equity=_decimal(documents.metrics, "final_equity"),
            realised_trade_count=_int(documents.metrics, "realised_trade_count"),
            open_position_count=_int(documents.metrics, "open_position_count"),
            gross_pnl=_decimal(documents.metrics, "gross_pnl"),
            fees_paid=_decimal(documents.metrics, "fees_paid"),
            net_pnl=_decimal(documents.metrics, "net_pnl"),
        )

    def _documents(self, run_id: str) -> _RunDocuments:
        try:
            manifest_raw = self._store.read_run_file(run_id, "manifest.json")
        except FileNotFoundError as exc:
            raise RunNotFound(run_id) from exc
        try:
            manifest = RunArtifactManifest.model_validate_json(manifest_raw)
        except ValidationError as exc:
            raise InvalidRunArtifact(str(exc), run_id=run_id) from exc

        payloads: dict[str, bytes] = {}
        for record in manifest.files:
            try:
                payload = self._store.read_run_file(run_id, record.path)
            except FileNotFoundError as exc:
                raise InvalidRunArtifact(
                    f"manifest file is missing: {record.path}", run_id=run_id
                ) from exc
            if len(payload) != record.size_bytes:
                raise InvalidRunArtifact(f"artifact size mismatch: {record.path}", run_id=run_id)
            if hashlib.sha256(payload).hexdigest() != record.sha256:
                raise InvalidRunArtifact(f"artifact hash mismatch: {record.path}", run_id=run_id)
            payloads[record.path] = payload

        try:
            request_raw = payloads["request.json"]
            result_raw = payloads["result.json"]
            metrics_raw = payloads["metrics.json"]
            request = SingleInstanceBacktestRequest.model_validate_json(request_raw)
            result = SingleInstanceBacktestResult.model_validate_json(result_raw)
            metrics = json.loads(metrics_raw)
        except (KeyError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise InvalidRunArtifact(str(exc), run_id=run_id) from exc
        if manifest.run_id != run_id or request.run_id != run_id or result.run_id != run_id:
            raise InvalidRunArtifact("run identity differs across artifact files", run_id=run_id)
        return _RunDocuments(manifest=manifest, request=request, result=result, metrics=metrics)

    @staticmethod
    def _summary(documents: _RunDocuments) -> RunSummary:
        market = documents.request.strategy.market
        strategy = documents.request.strategy
        return RunSummary(
            run_id=documents.manifest.run_id,
            created_at_utc=documents.manifest.created_at_utc,
            instance_id=documents.manifest.instance_id,
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.strategy_version,
            ticker=market.ticker,
            timeframe=market.timeframe,
            from_ms=market.from_ms,
            to_ms=market.to_ms,
            realised_trade_count=_int(documents.metrics, "realised_trade_count"),
            open_position_count=_int(documents.metrics, "open_position_count"),
            final_equity=_decimal(documents.metrics, "final_equity"),
            net_pnl=_decimal(documents.metrics, "net_pnl"),
            market_data_hash=documents.manifest.market_data_hash,
        )
