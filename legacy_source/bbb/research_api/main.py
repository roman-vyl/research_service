"""Research Workbench BFF — ``uvicorn research_api.main:app --reload``."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_api.routers import market, research_backtests, research_config, research_runs

app = FastAPI(title="Research Workbench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research_runs.router)
app.include_router(research_config.router)
app.include_router(research_backtests.router)
app.include_router(market.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
