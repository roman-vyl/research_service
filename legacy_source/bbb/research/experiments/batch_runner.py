"""Experiment BatchRunner v1 — sequential batch execution module."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from research.experiments.models import ExperimentBatchResult, ExperimentCandidateResult, ValidatedBatchSpec
from research.experiments.storage import write_batch_result
from research.experiments.summary import apply_summary_to_result, extract_candidate_summary
from research.experiments.validation import _repo_root, _relative_or_posix

RunCandidateFn = Callable[[str | Path, str], tuple[str, Path, Path]]


class BatchRunner:
    """Experiment BatchRunner v1 — runs validated candidates sequentially."""

    def __init__(
        self,
        *,
        run_candidate: RunCandidateFn | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._repo_root = repo_root if repo_root is not None else _repo_root()
        self._run_candidate = run_candidate if run_candidate is not None else _default_run_candidate

    def run(self, validated: ValidatedBatchSpec) -> ExperimentBatchResult:
        batch_started = datetime.now(timezone.utc)
        results: list[ExperimentCandidateResult] = []

        for candidate in validated.candidates:
            results.append(self._run_one(candidate, repo_root=self._repo_root, run_candidate=self._run_candidate))

        batch_finished = datetime.now(timezone.utc)
        ok_count = sum(1 for result in results if result.status == "ok")
        failed_count = len(results) - ok_count

        return ExperimentBatchResult(
            experiment_id=validated.spec.experiment_id,
            created_at=_format_ts(batch_finished),
            family=validated.spec.family,
            symbol=validated.spec.symbol,
            timeframe=validated.spec.timeframe,
            candidates_count=len(results),
            ok_count=ok_count,
            failed_count=failed_count,
            results=results,
            batch_spec_path=validated.batch_spec_path,
            batch_spec_hash=validated.batch_spec_hash,
            started_at=_format_ts(batch_started),
            finished_at=_format_ts(batch_finished),
            duration_sec=(batch_finished - batch_started).total_seconds(),
        )

    def run_and_persist(self, validated: ValidatedBatchSpec) -> tuple[ExperimentBatchResult, Path]:
        result = self.run(validated)
        output_path = write_batch_result(result)
        rel_path = _relative_or_posix(output_path, self._repo_root)
        return result, Path(rel_path)

    @staticmethod
    def _run_one(
        candidate,
        *,
        repo_root: Path,
        run_candidate: RunCandidateFn,
    ) -> ExperimentCandidateResult:
        started = datetime.now(timezone.utc)
        result = ExperimentCandidateResult(
            candidate_id=candidate.spec.candidate_id,
            status="failed",
            strategy_config_path=candidate.strategy_config_path,
            strategy_config_hash=candidate.strategy_config_hash,
            started_at=_format_ts(started),
        )

        config_path = Path(candidate.strategy_config_path)
        if not config_path.is_absolute():
            config_path = (repo_root / config_path).resolve()

        try:
            run_id, _latest_path, run_path = run_candidate(config_path, candidate.spec.candidate_id)
            if not run_path.exists():
                raise FileNotFoundError(f"strategy report not found: {run_path}")

            report_payload = json.loads(run_path.read_text(encoding="utf-8"))
            if not isinstance(report_payload, dict):
                raise ValueError("strategy report root must be a JSON object")

            summary = extract_candidate_summary(report_payload)
            apply_summary_to_result(result, summary)
            result.status = "ok"
            result.run_id = summary.get("run_id") or run_id
            result.report_path = _relative_or_posix(run_path, repo_root)
            summary_path = run_path.with_name(f"{run_id}.summary.json")
            if summary_path.exists():
                result.summary_report_path = _relative_or_posix(summary_path, repo_root)
            result.error = None
        except Exception as exc:  # noqa: BLE001 — runtime failure isolation per spec
            result.error = str(exc)

        finished = datetime.now(timezone.utc)
        result.finished_at = _format_ts(finished)
        result.duration_sec = (finished - started).total_seconds()
        return result


def _default_run_candidate(config_path: str | Path, candidate_id: str) -> tuple[str, Path, Path]:
    from research.strategies.ema_pullback.execution.runner import (
        run_strategy_specs_from_config_returning_paths,
    )

    return run_strategy_specs_from_config_returning_paths(
        config_path,
        run_id_suffix=candidate_id,
    )


def _format_ts(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
