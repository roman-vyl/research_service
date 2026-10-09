"""Stable service errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ResearchServiceError(Exception):
    code: str
    message: str
    status_code: int
    details: dict[str, Any] | None = None


class UpstreamServiceError(ResearchServiceError):
    def __init__(
        self,
        *,
        service: str,
        status_code: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="upstream_service_error",
            message=message,
            status_code=502 if status_code >= 500 else status_code,
            details={"service": service, "upstream_status": status_code, **(details or {})},
        )


class UpstreamResponse(Exception):
    """An upstream error response returned to the caller as it is: the same
    HTTP status and the same body (`research-market-ema-stack-episodes-v1`).
    Unlike `UpstreamServiceError`, the status is not rewritten and the
    error code is the upstream's own."""

    def __init__(self, *, service: str, status_code: int, body: object) -> None:
        super().__init__(f"{service} answered HTTP {status_code}")
        self.service = service
        self.status_code = status_code
        self.body = body


class InvalidRequest(ResearchServiceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="invalid_request",
            message=message,
            status_code=400,
            details=details,
        )


class DependencyUnavailable(ResearchServiceError):
    def __init__(
        self,
        *,
        service: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="dependency_unavailable",
            message=message,
            status_code=503,
            details={"service": service, **(details or {})},
        )


class RunAlreadyExists(ResearchServiceError):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            code="run_already_exists",
            message=f"research run already exists: {run_id}",
            status_code=409,
            details={"run_id": run_id},
        )


class RunNotFound(ResearchServiceError):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            code="run_not_found",
            message=f"research run not found: {run_id}",
            status_code=404,
            details={"run_id": run_id},
        )


class InvalidRunArtifact(ResearchServiceError):
    def __init__(self, message: str, *, run_id: str | None = None) -> None:
        details = {"run_id": run_id} if run_id is not None else None
        super().__init__(
            code="invalid_run_artifact",
            message=message,
            status_code=500,
            details=details,
        )


class DiagnosticsNotYetGenerated(ResearchServiceError):
    """Run exists but has no diagnostic artifact yet -- distinct from an
    error: a stable "not yet generated" state
    (research-diagnostics-projection-v1)."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            code="diagnostics_not_yet_generated",
            message=f"diagnostics have not been generated for run {run_id}",
            status_code=404,
            details={"run_id": run_id},
        )


class ManagedPolicyTraceUnavailable(ResearchServiceError):
    """Run's artifact bundle predates managed_policy_events.json. Not "no
    events" — a distinct "we cannot know" state for legacy bundles."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            code="managed_policy_trace_unavailable",
            message=(
                f"managed-policy trace unavailable for run {run_id}: "
                "artifact bundle predates managed_policy_events.json"
            ),
            status_code=404,
            details={"run_id": run_id},
        )


class ExperimentNotFound(ResearchServiceError):
    def __init__(self, experiment_id: str) -> None:
        super().__init__(
            code="experiment_not_found",
            message=f"experiment not found: {experiment_id}",
            status_code=404,
            details={"experiment_id": experiment_id},
        )


class InvalidExperiment(ResearchServiceError):
    def __init__(self, experiment_id: str, problem: str) -> None:
        super().__init__(
            code="experiment_invalid",
            message=f"experiment {experiment_id} is not readable: {problem}",
            status_code=500,
            details={"experiment_id": experiment_id, "problem": problem},
        )


class PlanStale(ResearchServiceError):
    def __init__(self, experiment_id: str, operation: str = "delete") -> None:
        super().__init__(
            code="plan_stale",
            message=f"the {operation} plan no longer matches the selection or the result table; plan again",
            status_code=409,
            details={"experiment_id": experiment_id},
        )


class InvalidCoords(ResearchServiceError):
    def __init__(self, experiment_id: str, problem: str) -> None:
        super().__init__(
            code="invalid_coords",
            message=f"coordinates do not fit experiment {experiment_id}: {problem}",
            status_code=400,
            details={"experiment_id": experiment_id, "problem": problem},
        )


class RowNotFound(ResearchServiceError):
    def __init__(self, experiment_id: str, coords: dict[str, str | None]) -> None:
        super().__init__(
            code="row_not_found",
            message=f"no row of experiment {experiment_id} has these coordinates",
            status_code=404,
            details={"experiment_id": experiment_id, "coords": coords},
        )


class AmbiguousRow(ResearchServiceError):
    def __init__(self, experiment_id: str, coords: dict[str, str | None], rows: int) -> None:
        super().__init__(
            code="ambiguous_row",
            message=f"{rows} rows of experiment {experiment_id} have these coordinates",
            status_code=409,
            details={"experiment_id": experiment_id, "coords": coords, "rows": rows},
        )


class InvalidCandidatesFile(ResearchServiceError):
    def __init__(self, problem: str) -> None:
        super().__init__(
            code="invalid_candidates_file",
            message=f"candidates.json is not readable: {problem}",
            status_code=500,
            details={"problem": problem},
        )


class CalculationRejected(ResearchServiceError):
    """Calculate is not possible for the whole Experiment (`research-run-calculation-v1`)."""

    def __init__(self, experiment_id: str, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details={"experiment_id": experiment_id, **(details or {})},
        )


class TooManyRows(ResearchServiceError):
    def __init__(self, count: int, limit: int) -> None:
        super().__init__(
            code="too_many_rows",
            message=f"at most {limit} rows per request; got {count}",
            status_code=422,
            details={"count": count, "limit": limit},
        )


class CalculationJobNotFound(ResearchServiceError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            code="calculation_job_not_found",
            message=f"calculation job not found: {job_id}",
            status_code=404,
            details={"job_id": job_id},
        )


class MarketDataHashMismatch(ResearchServiceError):
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            code="market_data_hash_mismatch",
            message=f"market data hash {actual} differs from the expected {expected}",
            status_code=409,
            details={"expected": expected, "actual": actual},
        )
