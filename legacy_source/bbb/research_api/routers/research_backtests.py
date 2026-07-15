"""``POST /api/research/backtests`` — sync research run from validated config."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from research_api.contracts.backtests import BacktestResult, RunBacktestRequest
from research_api.services.backtest_service import run_backtest

router = APIRouter(prefix="/api/research", tags=["research-backtests"])


@router.post("/backtests", response_model=BacktestResult)
def post_backtest(body: RunBacktestRequest) -> BacktestResult:
    try:
        return run_backtest(draft=body.draft, config_path=body.config_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
