from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.ports.strategy_engine import IndicatorSeriesResult
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


class FakeStrategyEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[object, int]] = []

    def health(self) -> bool:
        return True

    def evaluate_ema(self, market, *, period: int) -> IndicatorSeriesResult:
        self.calls.append((market, period))
        times = tuple(range(market.from_ms, market.to_ms, market.step_ms))
        values = tuple(str(index + 1) for index, _ in enumerate(times))
        return IndicatorSeriesResult(times, values, "plan", "market")


class HealthyMarket:
    def health(self) -> bool:
        return True


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def make_client(tmp_path: Path, strategy: FakeStrategyEngine) -> TestClient:
    settings = Settings(artifacts_root=tmp_path)
    return TestClient(
        create_app(
            settings,
            Container(settings, strategy, HealthyMarket(), ArtifactStore(tmp_path)),
        )
    )


def test_ema_window_preserves_dto_and_uses_strategy_engine(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    response = client.get(
        "/api/market/ema-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "period": 200,
            "from": 0,
            "to": 600_000,
        },
    )
    assert response.status_code == 200
    assert len(strategy.calls) == 1
    market, period = strategy.calls[0]
    assert market.ticker == "BTCUSDT.P"
    assert period == 200
    assert response.json() == {
        "points": [
            {"time": 0, "value": 1.0, "kind": "chart_overlay_ema"},
            {"time": 300, "value": 2.0, "kind": "chart_overlay_ema"},
        ],
        "coverage": {
            "requested_from_ms": 0,
            "requested_to_ms": 600000,
            "actual_from_ms": 0,
            "actual_to_ms": 600000,
            "calculation_origin_ms": 0,
            "coverage_to_ms": 600000,
            "cache_hit": False,
            "truncated": False,
        },
    }


def test_ema_window_second_slice_is_cache_hit(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    params = {
        "symbol": "BTCUSDT.P",
        "timeframe": "5m",
        "period": 10,
        "from": 0,
        "to": 600_000,
    }
    assert client.get("/api/market/ema-window", params=params).status_code == 200
    second = client.get("/api/market/ema-window", params=params)
    assert second.status_code == 200
    assert second.json()["coverage"]["cache_hit"] is True
    assert len(strategy.calls) == 1


def test_ema_window_rejects_unsupported_origin_policy(tmp_path: Path) -> None:
    response = make_client(tmp_path, FakeStrategyEngine()).get(
        "/api/market/ema-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "period": 10,
            "from": 0,
            "to": 300_000,
            "origin_policy": "window",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
