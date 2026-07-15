"""System endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
def readiness(request: Request):
    container = request.app.state.container
    strategy_ok = container.strategy_engine.health()
    market_ok = container.market_data.health()
    ready = strategy_ok and market_ok
    payload = {
        "status": "ready" if ready else "not_ready",
        "dependencies": {
            "strategy_engine": strategy_ok,
            "market_data_service": market_ok,
        },
        "artifacts_root": str(container.artifacts.root),
    }
    if ready:
        return payload
    return JSONResponse(status_code=503, content=payload)
