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
                open_time_ms=open_time,
                open=Decimal("100") + index,
                high=Decimal("101") + index,
                low=Decimal("99") + index,
                close=Decimal("100.5") + index,
                volume=Decimal("10") + index,
            )
            for index, open_time in enumerate(range(market.from_ms, market.to_ms, market.step_ms))
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
        values = tuple(str(period + index / 10) for index, _ in enumerate(times))
        return IndicatorSeriesResult(times, values, f"plan-{period}", "market")


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def make_client(
    tmp_path: Path,
    market: FakeMarketData,
    strategy: FakeStrategyEngine,
) -> TestClient:
    settings = Settings(artifacts_root=tmp_path)
    return TestClient(
        create_app(
            settings,
            Container(settings, strategy, market, ArtifactStore(tmp_path)),
        )
    )


def test_chart_bundle_preserves_legacy_dto_and_composes_downstream_services(
    tmp_path: Path,
) -> None:
    market = FakeMarketData()
    strategy = FakeStrategyEngine()
    response = make_client(tmp_path, market, strategy).get(
        "/api/market/chart-bundle",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 0,
            "to": 600_000,
            "ema_fast": 20,
            "ema_anchor": 50,
            "ema_slow": 200,
        },
    )
    assert response.status_code == 200
    assert len(market.calls) == 1
    assert market.calls[0].ticker == "BTCUSDT.P"
    assert [period for _, period in strategy.calls] == [20, 50, 200]
    assert response.json() == {
        "candles": [
            {
                "time": 0,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            },
            {
                "time": 300,
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "volume": 11.0,
            },
        ],
        "ema_overlays": [
            {
                "role": "fast",
                "period": 20,
                "points": [
                    {"time": 0, "value": 20.0, "kind": "chart_overlay_ema"},
                    {"time": 300, "value": 20.1, "kind": "chart_overlay_ema"},
                ],
            },
            {
                "role": "anchor",
                "period": 50,
                "points": [
                    {"time": 0, "value": 50.0, "kind": "chart_overlay_ema"},
                    {"time": 300, "value": 50.1, "kind": "chart_overlay_ema"},
                ],
            },
            {
                "role": "slow",
                "period": 200,
                "points": [
                    {"time": 0, "value": 200.0, "kind": "chart_overlay_ema"},
                    {"time": 300, "value": 200.1, "kind": "chart_overlay_ema"},
                ],
            },
        ],
    }


def test_chart_bundle_reuses_ema_cache_across_repeated_requests(tmp_path: Path) -> None:
    market = FakeMarketData()
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, market, strategy)
    params = {
        "symbol": "BTCUSDT.P",
        "timeframe": "5m",
        "from": 0,
        "to": 600_000,
        "ema_fast": 20,
        "ema_anchor": 50,
        "ema_slow": 200,
    }
    assert client.get("/api/market/chart-bundle", params=params).status_code == 200
    assert client.get("/api/market/chart-bundle", params=params).status_code == 200
    assert len(market.calls) == 2
    assert len(strategy.calls) == 3


def test_chart_bundle_rejects_non_monotonic_anchor_stack(tmp_path: Path) -> None:
    response = make_client(tmp_path, FakeMarketData(), FakeStrategyEngine()).get(
        "/api/market/chart-bundle",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 0,
            "to": 600_000,
            "ema_fast": 50,
            "ema_anchor": 20,
            "ema_slow": 200,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


def test_chart_bundle_supports_to_open_time_ms(tmp_path: Path) -> None:
    market = FakeMarketData()
    response = make_client(tmp_path, market, FakeStrategyEngine()).get(
        "/api/market/chart-bundle",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "from": 0,
            "to_open_time_ms": 300_000,
            "ema_fast": 20,
            "ema_anchor": 50,
            "ema_slow": 200,
        },
    )
    assert response.status_code == 200
    assert market.calls[0].to_ms == 600_000
