"""Chart view models for Workbench (OHLC bars and indicator overlays)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Series kind tags — chart view layer only (not strategy features / not Data Engine store).
CHART_OVERLAY_EMA_KIND: Literal["chart_overlay_ema"] = "chart_overlay_ema"
AnchorStackEmaRole = Literal["fast", "anchor", "slow"]


class ChartBar(BaseModel):
    """Single OHLC bar for Lightweight Charts.

    ``time`` is Unix **seconds** (``Candle.open_time_ms // 1000``).
    """

    model_config = ConfigDict(extra="forbid")

    time: int = Field(description="Bar open time as Unix seconds (UTC).")
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class IndicatorPoint(BaseModel):
    """Indicator sample aligned to ``ChartBar.time``.

    ``kind`` marks view-layer overlays (e.g. ``chart_overlay_ema``). Not strategy
    feature columns and not Data Engine ``indicator_values``.
    """

    model_config = ConfigDict(extra="forbid")

    time: int = Field(description="Unix seconds (matches chart bar open time).")
    value: float
    kind: Literal["chart_overlay_ema"] = Field(
        default=CHART_OVERLAY_EMA_KIND,
        description="Overlay series discriminator for Workbench chart only.",
    )


class ChartEmaOverlay(BaseModel):
    """One anchor-stack EMA line for Workbench chart (overlay on candle closes)."""

    model_config = ConfigDict(extra="forbid")

    role: AnchorStackEmaRole
    period: int = Field(ge=1, description="EMA period (from run strategy_spec anchor_stack).")
    points: list[IndicatorPoint]


class ChartMarketBundle(BaseModel):
    """OHLC bars + anchor-stack chart overlay EMAs from a single storage read."""

    model_config = ConfigDict(extra="forbid")

    candles: list[ChartBar]
    ema_overlays: list[ChartEmaOverlay]


class CandlesWindowCoverage(BaseModel):
    """Coverage metadata for ``GET /api/market/candles-window``."""

    model_config = ConfigDict(extra="forbid")

    requested_from_ms: int = Field(ge=0, description="Client-requested window start (ms, inclusive).")
    requested_to_ms: int = Field(ge=0, description="Client-requested window end (ms, exclusive).")
    actual_from_ms: int = Field(ge=0, description="Earliest bar open time returned (ms).")
    actual_to_ms: int = Field(ge=0, description="Exclusive end of returned bars (ms).")
    truncated: bool = Field(
        description="True when requested bounds could not be fully satisfied at data edges.",
    )


class CandlesWindowBundle(BaseModel):
    """Windowed OHLC payload — candles only (no EMA overlays)."""

    model_config = ConfigDict(extra="forbid")

    candles: list[ChartBar]
    coverage: CandlesWindowCoverage


class EmaWindowCoverage(BaseModel):
    """Coverage and canonical EMA cache metadata for ``GET /api/market/ema-window``."""

    model_config = ConfigDict(extra="forbid")

    requested_from_ms: int = Field(ge=0)
    requested_to_ms: int = Field(ge=0)
    actual_from_ms: int = Field(ge=0)
    actual_to_ms: int = Field(ge=0)
    calculation_origin_ms: int = Field(
        ge=0,
        description="Canonical EMA series start (earliest candle open used for seeding).",
    )
    coverage_to_ms: int = Field(
        ge=0,
        description="Exclusive end through which canonical EMA points are materialized in cache.",
    )
    cache_hit: bool = Field(
        description="True when response sliced from cached canonical series without extension compute.",
    )
    truncated: bool = Field(
        description="True when requested bounds exceed available market data.",
    )


class EmaWindowBundle(BaseModel):
    """Windowed chart overlay EMA — one period per response (no candles)."""

    model_config = ConfigDict(extra="forbid")

    points: list[IndicatorPoint]
    coverage: EmaWindowCoverage
