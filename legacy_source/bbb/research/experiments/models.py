"""Batch Experiment Management System — batch spec and result contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping


class BatchValidationError(ValueError):
    """Raised when a batch spec or candidate config fails preflight validation."""


_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class ExperimentCandidateSpec:
    candidate_id: str
    strategy_config_path: str
    metadata: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "strategy_config_path": self.strategy_config_path,
        }
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        return payload


@dataclass(frozen=True)
class ExperimentBatchSpec:
    experiment_id: str
    family: str
    symbol: str
    timeframe: str
    candidates: tuple[ExperimentCandidateSpec, ...]
    description: str | None = None
    result_options: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "experiment_id": self.experiment_id,
            "family": self.family,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candidates": [candidate.to_payload() for candidate in self.candidates],
        }
        if self.description is not None:
            payload["description"] = self.description
        if self.result_options is not None:
            payload["result_options"] = self.result_options
        return payload


@dataclass
class ExperimentCandidateResult:
    candidate_id: str
    status: str
    strategy_config_path: str
    strategy_config_hash: str
    run_id: str | None = None
    report_path: str | None = None
    summary_report_path: str | None = None
    config_id: str | None = None
    report_schema_version: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_sec: float | None = None
    error: str | None = None
    total_trades: int | None = None
    pnl: float | None = None
    return_pct: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    gross_pnl: float | None = None
    fees_paid: float | None = None
    high_mfe_high_capture_count: int | None = None
    high_mfe_low_capture_count: int | None = None
    signal_exit_winners: int | None = None
    signal_exit_giveback_failures: int | None = None
    stop_loss_after_low_mfe: int | None = None
    stop_loss_after_bad_context: int | None = None
    long_trades: int | None = None
    long_pnl: float | None = None
    long_gross_pnl: float | None = None
    long_fees_paid: float | None = None
    long_profit_factor: float | None = None
    long_win_rate: float | None = None
    short_trades: int | None = None
    short_pnl: float | None = None
    short_gross_pnl: float | None = None
    short_fees_paid: float | None = None
    short_profit_factor: float | None = None
    short_win_rate: float | None = None
    aligned_trades: int | None = None
    aligned_pnl: float | None = None
    aligned_gross_pnl: float | None = None
    aligned_fees_paid: float | None = None
    aligned_profit_factor: float | None = None
    aligned_win_rate: float | None = None
    countertrend_trades: int | None = None
    countertrend_pnl: float | None = None
    countertrend_gross_pnl: float | None = None
    countertrend_fees_paid: float | None = None
    countertrend_profit_factor: float | None = None
    countertrend_win_rate: float | None = None
    neutral_trades: int | None = None
    neutral_pnl: float | None = None
    neutral_gross_pnl: float | None = None
    neutral_fees_paid: float | None = None
    neutral_profit_factor: float | None = None
    neutral_win_rate: float | None = None
    long_aligned_trades: int | None = None
    long_aligned_pnl: float | None = None
    long_aligned_gross_pnl: float | None = None
    long_aligned_fees_paid: float | None = None
    long_aligned_profit_factor: float | None = None
    long_aligned_win_rate: float | None = None
    long_countertrend_trades: int | None = None
    long_countertrend_pnl: float | None = None
    long_countertrend_gross_pnl: float | None = None
    long_countertrend_fees_paid: float | None = None
    long_countertrend_profit_factor: float | None = None
    long_countertrend_win_rate: float | None = None
    long_neutral_trades: int | None = None
    long_neutral_pnl: float | None = None
    long_neutral_gross_pnl: float | None = None
    long_neutral_fees_paid: float | None = None
    long_neutral_profit_factor: float | None = None
    long_neutral_win_rate: float | None = None
    short_aligned_trades: int | None = None
    short_aligned_pnl: float | None = None
    short_aligned_gross_pnl: float | None = None
    short_aligned_fees_paid: float | None = None
    short_aligned_profit_factor: float | None = None
    short_aligned_win_rate: float | None = None
    short_countertrend_trades: int | None = None
    short_countertrend_pnl: float | None = None
    short_countertrend_gross_pnl: float | None = None
    short_countertrend_fees_paid: float | None = None
    short_countertrend_profit_factor: float | None = None
    short_countertrend_win_rate: float | None = None
    short_neutral_trades: int | None = None
    short_neutral_pnl: float | None = None
    short_neutral_gross_pnl: float | None = None
    short_neutral_fees_paid: float | None = None
    short_neutral_profit_factor: float | None = None
    short_neutral_win_rate: float | None = None

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items()}


@dataclass
class ExperimentBatchResult:
    experiment_id: str
    created_at: str
    family: str
    symbol: str
    timeframe: str
    candidates_count: int
    ok_count: int
    failed_count: int
    results: list[ExperimentCandidateResult]
    batch_spec_path: str
    batch_spec_hash: str
    started_at: str
    finished_at: str
    duration_sec: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": self.duration_sec,
            "batch_spec_path": self.batch_spec_path,
            "batch_spec_hash": self.batch_spec_hash,
            "family": self.family,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candidates_count": self.candidates_count,
            "ok_count": self.ok_count,
            "failed_count": self.failed_count,
            "results": [result.to_payload() for result in self.results],
        }


@dataclass(frozen=True)
class ValidatedCandidate:
    spec: ExperimentCandidateSpec
    strategy_config_path: str
    strategy_config_hash: str


@dataclass(frozen=True)
class ValidatedBatchSpec:
    spec: ExperimentBatchSpec
    batch_spec_path: str
    batch_spec_hash: str
    candidates: tuple[ValidatedCandidate, ...]


def load_batch_spec(payload: Mapping[str, Any]) -> ExperimentBatchSpec:
    experiment_id = _require_safe_id(payload, "experiment_id")
    family = _require_non_empty_str(payload, "family")
    symbol = _require_non_empty_str(payload, "symbol").strip().upper()
    timeframe = _require_non_empty_str(payload, "timeframe").strip()
    description = payload.get("description")
    if description is not None and (not isinstance(description, str) or not description.strip()):
        raise BatchValidationError("description must be a non-empty string when provided")
    result_options = payload.get("result_options")
    if result_options is not None and not isinstance(result_options, dict):
        raise BatchValidationError("result_options must be an object")

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise BatchValidationError("candidates must be a non-empty list")

    candidates: list[ExperimentCandidateSpec] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_candidates):
        if not isinstance(item, Mapping):
            raise BatchValidationError(f"candidates[{index}] must be an object")
        candidate_id = _require_safe_id(item, "candidate_id", prefix=f"candidates[{index}].")
        if candidate_id in seen_ids:
            raise BatchValidationError(f"duplicate candidate_id in batch spec: {candidate_id!r}")
        seen_ids.add(candidate_id)
        strategy_config_path = _require_non_empty_str(
            item,
            "strategy_config_path",
            prefix=f"candidates[{index}].",
        )
        metadata = item.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise BatchValidationError(f"candidates[{index}].metadata must be an object")
        candidates.append(
            ExperimentCandidateSpec(
                candidate_id=candidate_id,
                strategy_config_path=strategy_config_path.strip(),
                metadata=metadata,
            )
        )

    return ExperimentBatchSpec(
        experiment_id=experiment_id,
        family=family,
        symbol=symbol,
        timeframe=timeframe,
        candidates=tuple(candidates),
        description=description.strip() if isinstance(description, str) else None,
        result_options=result_options,
    )


def validate_safe_experiment_id(experiment_id: str) -> str:
    if not _SAFE_ID_PATTERN.match(experiment_id):
        raise BatchValidationError(
            "experiment_id must match [A-Za-z0-9_.-]+ (no path separators or spaces)"
        )
    return experiment_id


def load_batch_spec_file(path: str | Path) -> ExperimentBatchSpec:
    source = Path(path)
    if not source.exists():
        raise BatchValidationError(f"batch spec file does not exist: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BatchValidationError(f"failed to parse batch spec JSON {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchValidationError("batch spec root must be a JSON object")
    return load_batch_spec(payload)


def _require_safe_id(
    payload: Mapping[str, Any],
    key: str,
    *,
    prefix: str = "",
) -> str:
    value = _require_non_empty_str(payload, key, prefix=prefix)
    if not _SAFE_ID_PATTERN.match(value):
        raise BatchValidationError(
            f"{prefix}{key} must match [A-Za-z0-9_.-]+ (no path separators or spaces)"
        )
    return value


def _require_non_empty_str(
    payload: Mapping[str, Any],
    key: str,
    *,
    prefix: str = "",
) -> str:
    if key not in payload:
        raise BatchValidationError(f"{prefix}{key} is required")
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise BatchValidationError(f"{prefix}{key} must be a non-empty string")
    return value.strip()
