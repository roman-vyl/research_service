from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.domain.contracts import Candle, MarketFrame, MarketRange
from research_service.ports.strategy_engine import IndicatorSeriesResult
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


class FakeMarketData:
    def __init__(self) -> None:
        self.calls: list[MarketRange] = []

    def health(self) -> bool:
        return True

    def read_range(self, market: MarketRange) -> MarketFrame:
        self.calls.append(market)
        candles = tuple(
            Candle(
                open_time_ms=ts,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.5"),
                volume=Decimal("10"),
            )
            for ts in range(market.from_ms, market.to_ms, market.step_ms)
        )
        return MarketFrame(market=market, candles=candles)


class FakeStrategyEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[MarketRange, int]] = []

    def health(self) -> bool:
        return True

    def evaluate_ema(self, market: MarketRange, *, period: int) -> IndicatorSeriesResult:
        self.calls.append((market, period))
        times = tuple(range(market.from_ms, market.to_ms, market.step_ms))
        values = tuple("42.5" for _ in times)
        return IndicatorSeriesResult(times, values, "plan", "market")


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def make_client(tmp_path: Path, market: FakeMarketData, strategy: FakeStrategyEngine) -> TestClient:
    settings = Settings(artifacts_root=tmp_path)
    return TestClient(
        create_app(
            settings,
            Container(settings, strategy, market, ArtifactStore(tmp_path)),
        )
    )


def test_candles_alias_returns_legacy_list_and_reuses_window_use_case(tmp_path: Path) -> None:
    market = FakeMarketData()
    strategy = FakeStrategyEngine()
    response = make_client(tmp_path, market, strategy).get(
        "/api/market/candles",
        params={"symbol": "BTCUSDT", "timeframe": "5m", "from": 0, "to": 600_000},
    )
    assert response.status_code == 200
    assert response.json() == [
        {"time": 0, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
        {"time": 300, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
    ]
    assert market.calls[0].ticker == "BTCUSDT.P"
    assert strategy.calls == []


def test_ema_alias_returns_legacy_list_and_reuses_shared_cache(tmp_path: Path) -> None:
    market = FakeMarketData()
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, market, strategy)
    params = {"symbol": "BTCUSDT", "timeframe": "5m", "period": 20, "from": 0, "to": 600_000}

    first = client.get("/api/market/indicators/ema", params=params)
    second = client.get("/api/market/indicators/ema", params=params)

    assert first.status_code == 200
    assert first.json() == [
        {"time": 0, "value": 42.5, "kind": "chart_overlay_ema"},
        {"time": 300, "value": 42.5, "kind": "chart_overlay_ema"},
    ]
    assert second.status_code == 200
    assert len(strategy.calls) == 1
    assert market.calls == []


def test_aliases_preserve_400_range_validation(tmp_path: Path) -> None:
    client = make_client(tmp_path, FakeMarketData(), FakeStrategyEngine())
    for path, extra in (
        ("/api/market/candles", {}),
        ("/api/market/indicators/ema", {"period": 20}),
    ):
        response = client.get(
            path,
            params={
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "from": 600_000,
                "to": 300_000,
                **extra,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"
