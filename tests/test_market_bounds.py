from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.domain.contracts import StreamBounds
from research_service.domain.errors import DependencyUnavailable, UpstreamServiceError
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


class FakeBoundsMarketData:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error = error

    def health(self) -> bool:
        return True

    def get_bounds(self, *, ticker: str, timeframe: str) -> StreamBounds:
        self.calls.append((ticker, timeframe))
        if self.error is not None:
            raise self.error
        return StreamBounds(
            ticker=ticker,
            timeframe=timeframe,
            earliest_open_time_ms=1_614_556_800_000,
            latest_open_time_ms=1_760_000_100_000,
            stream_state="ready",
        )


class HealthyStrategy:
    def health(self) -> bool:
        return True


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def client(tmp_path: Path, market_data: FakeBoundsMarketData) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(settings, HealthyStrategy(), market_data, ArtifactStore(tmp_path)),
        )
    )


def test_bounds_forwarded_with_exact_shape_and_canonical_ticker(tmp_path: Path) -> None:
    market_data = FakeBoundsMarketData()
    response = client(tmp_path, market_data).get(
        "/api/market/bounds", params={"symbol": "BTCUSDT", "timeframe": " 5m "}
    )
    assert response.status_code == 200
    assert market_data.calls == [("BTCUSDT.P", "5m")]
    assert response.json() == {
        "symbol": "BTCUSDT.P",
        "timeframe": "5m",
        "earliest_open_time_ms": 1_614_556_800_000,
        "latest_open_time_ms": 1_760_000_100_000,
        "stream_state": "ready",
    }


def test_bounds_keeps_dot_p_ticker_and_asks_port_on_every_request(tmp_path: Path) -> None:
    market_data = FakeBoundsMarketData()
    http = client(tmp_path, market_data)
    params = {"symbol": "ETHUSDT.P", "timeframe": "15m"}
    assert http.get("/api/market/bounds", params=params).json()["symbol"] == "ETHUSDT.P"
    http.get("/api/market/bounds", params=params)
    assert market_data.calls == [("ETHUSDT.P", "15m")] * 2


def test_bounds_invalid_symbol_is_400_without_port_call(tmp_path: Path) -> None:
    market_data = FakeBoundsMarketData()
    response = client(tmp_path, market_data).get(
        "/api/market/bounds", params={"symbol": "BTC/USDT", "timeframe": "5m"}
    )
    assert response.status_code == 400
    assert market_data.calls == []


@pytest.mark.parametrize("timeframe", ["7x", "2m", "xx"])
def test_bounds_unsupported_timeframe_is_400_without_port_call(
    tmp_path: Path, timeframe: str
) -> None:
    market_data = FakeBoundsMarketData()
    response = client(tmp_path, market_data).get(
        "/api/market/bounds", params={"symbol": "BTCUSDT", "timeframe": timeframe}
    )
    assert response.status_code == 400
    assert len(market_data.calls) == 0


def test_bounds_dependency_unavailable_is_503(tmp_path: Path) -> None:
    market_data = FakeBoundsMarketData(DependencyUnavailable(service="market-data", message="down"))
    response = client(tmp_path, market_data).get(
        "/api/market/bounds", params={"symbol": "BTCUSDT", "timeframe": "5m"}
    )
    assert response.status_code == 503


def test_bounds_upstream_404_passes_through(tmp_path: Path) -> None:
    market_data = FakeBoundsMarketData(
        UpstreamServiceError(service="market-data", status_code=404, message="unknown stream")
    )
    response = client(tmp_path, market_data).get(
        "/api/market/bounds", params={"symbol": "BTCUSDT", "timeframe": "5m"}
    )
    assert response.status_code == 404
