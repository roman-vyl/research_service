"""Batch Experiment Management System — batch result persistence."""

from __future__ import annotations

import json
from pathlib import Path

from research.experiments.models import BatchValidationError, ExperimentBatchResult, validate_safe_experiment_id


def default_batches_dir() -> Path:
    return Path(__file__).resolve().parent / "results" / "batches"


def batch_result_path(experiment_id: str, *, batches_dir: Path | None = None) -> Path:
    validate_safe_experiment_id(experiment_id)
    base = batches_dir if batches_dir is not None else default_batches_dir()
    return base / f"{experiment_id}.json"


def write_batch_result(result: ExperimentBatchResult, *, batches_dir: Path | None = None) -> Path:
    path = batch_result_path(result.experiment_id, batches_dir=batches_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_payload(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def read_batch_result(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("batch result root must be a JSON object")
    return payload
