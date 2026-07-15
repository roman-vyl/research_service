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


class CapabilityNotPorted(ResearchServiceError):
    def __init__(self, capability: str) -> None:
        super().__init__(
            code="capability_not_ported",
            message=f"{capability} is preserved but not ported yet",
            status_code=501,
            details={"capability": capability},
        )


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
