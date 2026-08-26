from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.application.market import canonical_ticker
from research_service.domain.contracts import Candle, MarketFrame, MarketRange
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


class FakeMarketData:
    def __init__(self) -> None:
        self.requested: MarketRange | None = None

    def health(self) -> bool:
        return True

    def read_range(self, market: MarketRange) -> MarketFrame:
        self.requested = market
        candles = tuple(
            Candle(
                open_time_ms=open_time,
                open=Decimal("100.25") + index,
                high=Decimal("101.5") + index,
                low=Decimal("99.5") + index,
                close=Decimal("100.75") + index,
                volume=Decimal("10.25") + index,
            )
            for index, open_time in enumerate(range(market.from_ms, market.to_ms, market.step_ms))
        )
        return MarketFrame(market=market, candles=candles)


class HealthyStrategy:
    def health(self) -> bool:
        return True


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def client(tmp_path: Path, market_data: FakeMarketData) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(
                settings,
                HealthyStrategy(),
                market_data,
                ArtifactStore(tmp_path),
            ),
        )
    )


def test_candles_window_preserves_workbench_dto_and_maps_legacy_symbol(
    tmp_path: Path,
) -> None:
    market_data = FakeMarketData()
    response = client(tmp_path, market_data).get(
        "/api/market/candles-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 0,
            "to": 600_000,
        },
    )
    assert response.status_code == 200
    assert market_data.requested == MarketRange(
        ticker="BTCUSDT.P",
        timeframe="5m",
        from_ms=0,
        to_ms=600_000,
    )
    assert response.json() == {
        "candles": [
            {
                "time": 0,
                "open": 100.25,
                "high": 101.5,
                "low": 99.5,
                "close": 100.75,
                "volume": 10.25,
            },
            {
                "time": 300,
                "open": 101.25,
                "high": 102.5,
                "low": 100.5,
                "close": 101.75,
                "volume": 11.25,
            },
        ],
        "coverage": {
            "requested_from_ms": 0,
            "requested_to_ms": 600_000,
            "actual_from_ms": 0,
            "actual_to_ms": 600_000,
            "truncated": False,
        },
    }


def test_candles_window_supports_to_open_time_ms(tmp_path: Path) -> None:
    market_data = FakeMarketData()
    response = client(tmp_path, market_data).get(
        "/api/market/candles-window",
        params={
            "symbol": "BTCUSDT.P",
            "timeframe": "5m",
            "from": 0,
            "to_open_time_ms": 300_000,
        },
    )
    assert response.status_code == 200
    assert market_data.requested is not None
    assert market_data.requested.to_ms == 600_000


def test_candles_window_validation_remains_400(tmp_path: Path) -> None:
    market_data = FakeMarketData()
    api = client(tmp_path, market_data)
    both = api.get(
        "/api/market/candles-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 0,
            "to": 300_000,
            "to_open_time_ms": 0,
        },
    )
    assert both.status_code == 400
    assert both.json()["error"] == "invalid_request"

    reversed_range = api.get(
        "/api/market/candles-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 300_000,
            "to": 0,
        },
    )
    assert reversed_range.status_code == 400


def test_canonical_ticker_rejects_invalid_symbols() -> None:
    assert canonical_ticker("btcusdt") == "BTCUSDT.P"
    assert canonical_ticker("BTCUSDT.P") == "BTCUSDT.P"
