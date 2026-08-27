"""Resolve and verify the immutable market window used by one backtest."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.contracts import ContinuityAudit, ExplicitRange, MarketRange, timeframe_ms
from research_service.domain.errors import InvalidRequest
from research_service.ports.market_data import MarketDataPort


class ResolvedBacktestWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_history_window.v1"] = "research_history_window.v1"
    range_policy: Literal["explicit_range", "full_available"]
    market: MarketRange
    expected_bar_count: int = Field(ge=1)
    stream_state: str
    audit: ContinuityAudit
    market_data_hash: str


class ResolveBacktestWindow:
    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data

    def execute(
        self,
        *,
        ticker: str,
        timeframe: str,
        explicit_range: ExplicitRange | None,
        range_policy: Literal["explicit_range", "full_available"],
    ) -> ResolvedBacktestWindow:
        if range_policy == "explicit_range":
            if explicit_range is None:
                raise InvalidRequest("range_policy=explicit_range requires from_ms/to_ms")
            market = MarketRange(
                ticker=ticker,
                timeframe=timeframe,
                from_ms=explicit_range.from_ms,
                to_ms=explicit_range.to_ms,
            )
        else:
            if explicit_range is not None:
                raise InvalidRequest("range_policy=full_available must not include a range")
            bounds = self._market_data.get_bounds(ticker=ticker, timeframe=timeframe)
            market = MarketRange(
                ticker=bounds.ticker,
                timeframe=bounds.timeframe,
                from_ms=bounds.earliest_open_time_ms,
                to_ms=bounds.latest_open_time_ms + timeframe_ms(timeframe),
            )
        audit = self._market_data.audit_range(market)
        if audit.market != market:
            raise InvalidRequest(
                "Market Data Service audit range does not match the requested range"
            )
        if not audit.is_continuous:
            raise InvalidRequest(
                "market range is not continuous",
                details={
                    "code": "market_range_not_continuous",
                    "gaps": [gap.model_dump() for gap in audit.gaps],
                },
            )
        if not audit.market_data_hash:
            raise InvalidRequest("Market Data Service audit lacks market_data_hash")
        expected_bar_count = (market.to_ms - market.from_ms) // market.step_ms
        if audit.candle_count != expected_bar_count:
            raise InvalidRequest("Market Data Service audit candle count does not match the range")
        return ResolvedBacktestWindow(
            range_policy=range_policy,
            market=market,
            expected_bar_count=expected_bar_count,
            stream_state=audit.stream_state,
            audit=audit,
            market_data_hash=audit.market_data_hash,
        )
