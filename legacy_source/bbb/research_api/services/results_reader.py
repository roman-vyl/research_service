"""Read research run JSON artifacts from ``research/results/``."""

from __future__ import annotations

import json
from pathlib import Path

from research_api.contracts.runs import (
    SUPPORTED_REPORT_SCHEMA_VERSIONS,
    RunCompactSummaryReport,
    RunReport,
    RunSummary,
)
from research_api.services.run_id import validate_run_id


class ResultsNotFoundError(FileNotFoundError):
    """Run artifact file is missing."""


class UnsupportedSchemaVersionError(ValueError):
    """``report_schema_version`` is not whitelisted for Workbench."""

    def __init__(self, version: int | None) -> None:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_REPORT_SCHEMA_VERSIONS))
        super().__init__(
            f"Unsupported report_schema_version {version!r}. Supported: {supported}.",
        )
        self.version = version


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_results_dir() -> Path:
    return repo_root() / "research" / "results"


def _runs_dir(results_dir: Path | None = None) -> Path:
    base = results_dir if results_dir is not None else default_results_dir()
    return base / "runs"


def _assert_supported_schema(version: int | None) -> None:
    if version not in SUPPORTED_REPORT_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError(version)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise ResultsNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_run_report(payload: dict) -> RunReport:
    _assert_supported_schema(payload.get("report_schema_version"))
    return RunReport.model_validate(payload)


def parse_run_summary_report(payload: dict) -> RunCompactSummaryReport:
    _assert_supported_schema(payload.get("report_schema_version"))
    return RunCompactSummaryReport.model_validate(payload)


def load_run_report(*, run_id: str, results_dir: Path | None = None) -> RunReport:
    safe_run_id = validate_run_id(run_id)
    path = _runs_dir(results_dir) / f"{safe_run_id}.json"
    return parse_run_report(_load_json(path))


def load_run_summary_report(*, run_id: str, results_dir: Path | None = None) -> RunCompactSummaryReport:
    safe_run_id = validate_run_id(run_id)
    path = _runs_dir(results_dir) / f"{safe_run_id}.summary.json"
    return parse_run_summary_report(_load_json(path))


def load_latest_run_report(results_dir: Path | None = None) -> RunReport:
    base = results_dir if results_dir is not None else default_results_dir()
    path = base / "latest.json"
    return parse_run_report(_load_json(path))


def summary_from_payload(payload: dict) -> RunSummary:
    return RunSummary(
        run_id=str(payload["run_id"]),
        created_at=str(payload["created_at"]),
        family=str(payload["family"]),
        symbol=str(payload["symbol"]),
        timeframe=str(payload["timeframe"]),
    )


def list_run_summaries(results_dir: Path | None = None) -> list[RunSummary]:
    runs = _runs_dir(results_dir)
    if not runs.is_dir():
        return []

    summaries: dict[str, RunSummary] = {}
    for path in sorted(runs.glob("*.json")):
        payload = _load_json(path)
        _assert_supported_schema(payload.get("report_schema_version"))
        summary = summary_from_payload(payload)
        summaries[summary.run_id] = summary

    return sorted(summaries.values(), key=lambda s: s.created_at, reverse=True)
