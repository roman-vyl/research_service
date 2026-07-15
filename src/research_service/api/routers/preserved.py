"""Preserved Workbench/BFF routes awaiting semantic port."""

from __future__ import annotations

from fastapi import APIRouter

from research_service.domain.errors import CapabilityNotPorted

router = APIRouter()


def _not_ported(capability: str) -> None:
    raise CapabilityNotPorted(capability)


@router.get("/api/market/candles")
def candles() -> None:
    _not_ported("market.candles")


@router.get("/api/market/indicators/ema")
def ema_points() -> None:
    _not_ported("market.indicators.ema")
