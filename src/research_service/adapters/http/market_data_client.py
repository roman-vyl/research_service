"""HTTP adapter for Market Data Service runtime and historical contracts."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field

from research_service.application.backtests.history_window import (
    ContinuityAudit,
    GapRange,
    StreamBounds,
)
from research_service.domain.contracts import Candle, MarketFrame, MarketRange
from research_service.domain.errors import DependencyUnavailable, UpstreamServiceError


class _BoundsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    ticker: str
    timeframe: str
    state: str
    earliest_committed_open_time_ms: int = Field(ge=0)
    latest_committed_open_time_ms: int = Field(ge=0)


class _AuditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    ticker: str
    timeframe: str
    checked_start_ms: int = Field(ge=0)
    checked_end_ms: int = Field(gt=0)
    candle_count: int = Field(ge=0)
    is_continuous: bool
    gaps: list[dict[str, int]]
    state: str
    market_data_hash: str | None = None


class _CandleRangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    timeframe: str
    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)
    market_data_hash: str
    candles: list[Candle]


class HttpMarketDataClient:
    def __init__(self, base_url: str, timeout_seconds: float = 60.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def health(self) -> bool:
        try:
            response = self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def get_bounds(self, *, ticker: str, timeframe: str) -> StreamBounds:
        response = self._request(
            "GET",
            f"/v1/streams/{ticker}/{timeframe}/bounds",
        )
        payload = _BoundsPayload.model_validate(response.json())
        return StreamBounds(
            ticker=payload.ticker,
            timeframe=payload.timeframe,
            earliest_open_time_ms=payload.earliest_committed_open_time_ms,
            latest_open_time_ms=payload.latest_committed_open_time_ms,
            stream_state=payload.state,
        )

    def audit_range(self, market: MarketRange) -> ContinuityAudit:
        response = self._request(
            "POST",
            f"/v1/streams/{market.ticker}/{market.timeframe}/continuity-audits",
            json={"from_ms": market.from_ms, "to_ms": market.to_ms},
        )
        payload = _AuditPayload.model_validate(response.json())
        returned = MarketRange(
            ticker=payload.ticker,
            timeframe=payload.timeframe,
            from_ms=payload.checked_start_ms,
            to_ms=payload.checked_end_ms,
        )
        return ContinuityAudit(
            contract_version="market_continuity_audit.v1",
            market=returned,
            candle_count=payload.candle_count,
            is_continuous=payload.is_continuous,
            gaps=tuple(GapRange.model_validate(item) for item in payload.gaps),
            stream_state=payload.state,
            market_data_hash=payload.market_data_hash,
        )

    def read_historical_range(
        self,
        market: MarketRange,
        *,
        expected_market_data_hash: str,
    ) -> MarketFrame:
        response = self._request(
            "POST",
            "/v1/historical-candles",
            json={
                "ticker": market.ticker,
                "timeframe": market.timeframe,
                "from_ms": market.from_ms,
                "to_ms": market.to_ms,
                "expected_market_data_hash": expected_market_data_hash,
            },
        )
        return self._decode_frame(response, market, expected_market_data_hash)

    def read_range(self, market: MarketRange) -> MarketFrame:
        response = self._request(
            "GET",
            "/v1/candles",
            params={
                "ticker": market.ticker,
                "timeframe": market.timeframe,
                "from_ms": market.from_ms,
                "to_ms": market.to_ms,
            },
        )
        return self._decode_frame(response, market, None)

    def _decode_frame(
        self,
        response: httpx.Response,
        market: MarketRange,
        expected_hash: str | None,
    ) -> MarketFrame:
        payload = _CandleRangePayload.model_validate(response.json())
        returned = MarketRange(
            ticker=payload.ticker,
            timeframe=payload.timeframe,
            from_ms=payload.from_ms,
            to_ms=payload.to_ms,
        )
        if returned != market:
            raise UpstreamServiceError(
                service="market_data_service",
                status_code=502,
                message="Market Data Service response identity mismatch",
            )
        if expected_hash is not None and payload.market_data_hash != expected_hash:
            raise UpstreamServiceError(
                service="market_data_service",
                status_code=409,
                message="Market Data Service historical snapshot changed",
                details={"code": "market_data_hash_mismatch"},
            )
        return MarketFrame(
            market=market,
            candles=tuple(payload.candles),
            market_data_hash=payload.market_data_hash,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable(
                service="market_data_service",
                message=str(exc),
            ) from exc
        if response.status_code >= 500:
            raise DependencyUnavailable(
                service="market_data_service",
                message="Market Data Service request failed",
                details={
                    "upstream_status": response.status_code,
                    "body": _safe_json(response),
                },
            )
        if response.status_code != 200:
            raise UpstreamServiceError(
                service="market_data_service",
                status_code=response.status_code,
                message="Market Data Service request failed",
                details={"body": _safe_json(response)},
            )
        return response


def _safe_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return response.text
