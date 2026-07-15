"""Workbench chart transport contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChartBar(BaseModel):
    """Single Lightweight Charts OHLCV bar."""

    model_config = ConfigDict(extra="forbid")

    time: int = Field(description="Bar open time as Unix seconds (UTC).")
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class CandlesWindowCoverage(BaseModel):
    """Coverage metadata retained from the BBB Workbench contract."""

    model_config = ConfigDict(extra="forbid")

    requested_from_ms: int = Field(ge=0)
    requested_to_ms: int = Field(ge=0)
    actual_from_ms: int = Field(ge=0)
    actual_to_ms: int = Field(ge=0)
    truncated: bool


class CandlesWindowBundle(BaseModel):
    """Windowed candle payload used by Workbench."""

    model_config = ConfigDict(extra="forbid")

    candles: list[ChartBar]
    coverage: CandlesWindowCoverage


class IndicatorPoint(BaseModel):
    """Indicator sample aligned to chart time."""

    model_config = ConfigDict(extra="forbid")

    time: int
    value: float
    kind: str = "chart_overlay_ema"


class EmaWindowCoverage(BaseModel):
    """Legacy-compatible EMA window metadata."""

    model_config = ConfigDict(extra="forbid")

    requested_from_ms: int = Field(ge=0)
    requested_to_ms: int = Field(ge=0)
    actual_from_ms: int = Field(ge=0)
    actual_to_ms: int = Field(ge=0)
    calculation_origin_ms: int = Field(ge=0)
    coverage_to_ms: int = Field(ge=0)
    cache_hit: bool
    truncated: bool


class EmaWindowBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[IndicatorPoint]
    coverage: EmaWindowCoverage


class ChartEmaOverlay(BaseModel):
    """One anchor-stack EMA overlay in the preserved Workbench bundle."""

    model_config = ConfigDict(extra="forbid")

    role: str
    period: int = Field(ge=1)
    points: list[IndicatorPoint]


class ChartMarketBundle(BaseModel):
    """Legacy monolithic OHLC plus anchor-stack EMA payload."""

    model_config = ConfigDict(extra="forbid")

    candles: list[ChartBar]
    ema_overlays: list[ChartEmaOverlay]
