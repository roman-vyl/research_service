"""FastAPI exception mapping."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from research_service.domain.errors import ResearchServiceError


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
