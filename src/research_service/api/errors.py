"""FastAPI exception mapping."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from research_service.domain.errors import ResearchServiceError, UpstreamResponse


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ResearchServiceError)
    async def handle_service_error(
        request: Request,
        exc: ResearchServiceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details or {},
                "request_id": request.headers.get("x-request-id", str(uuid4())),
            },
        )

    @app.exception_handler(UpstreamResponse)
    async def handle_upstream_response(
        request: Request,
        exc: UpstreamResponse,
    ) -> JSONResponse:
        if isinstance(exc.body, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.body)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "upstream_service_error",
                "message": f"{exc.service} answered HTTP {exc.status_code}",
                "details": {
                    "service": exc.service,
                    "upstream_status": exc.status_code,
                    "body": exc.body,
                },
                "request_id": request.headers.get("x-request-id", str(uuid4())),
            },
        )
