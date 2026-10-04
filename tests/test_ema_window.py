from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.application.market.ema_window import GetEmaWindow
from research_service.domain.contracts import MarketRange, StreamBounds
from research_service.ports.strategy_engine import (
    IndicatorSeriesResult,
    MultiIndicatorSeriesResult,
)
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container

STEP_MS = 300_000
REQUEST_FROM_MS = 1_800_000_000
REQUEST_TO_MS = REQUEST_FROM_MS + 2 * STEP_MS
PREVIEW_FROM_MS = REQUEST_FROM_MS - 5_000 * STEP_MS
FULL_TO_MS = REQUEST_TO_MS + 10 * STEP_MS


class FakeStrategyEngine:
    def __init__(
        self,
        *,
        block_full: bool = True,
        block_preview: bool = False,
        fail_full_count: int = 0,
    ) -> None:
        self.multi_calls: list[tuple[MarketRange, tuple[int, ...]]] = []
        self.single_calls: list[tuple[MarketRange, int]] = []
        self.full_started = Event()
        self.release_full = Event()
        self.preview_started = Event()
        self.release_preview = Event()
        self.block_full = block_full
        self.block_preview = block_preview
        self.fail_full_count = fail_full_count
        self._lock = Lock()

    def health(self) -> bool:
        return True

    def evaluate_ema(self, market: MarketRange, *, period: int) -> IndicatorSeriesResult:
        with self._lock:
            self.single_calls.append((market, period))
        times = tuple(range(market.from_ms, market.to_ms, market.step_ms))
        values = tuple(str(period + index) for index, _ in enumerate(times))
        return IndicatorSeriesResult(times, values, "single-plan", "market")

    def evaluate_emas(
        self,
        market: MarketRange,
        *,
        periods: tuple[int, ...],
    ) -> MultiIndicatorSeriesResult:
        with self._lock:
            self.multi_calls.append((market, periods))
            is_full = market.from_ms == 0 and market.to_ms == FULL_TO_MS
            fail = is_full and self.fail_full_count > 0
            if fail:
                self.fail_full_count -= 1
        if is_full:
            self.full_started.set()
            if fail:
                raise RuntimeError("full build failed")
            if self.block_full:
                assert self.release_full.wait(timeout=5)
        elif self.block_preview:
            self.preview_started.set()
            assert self.release_preview.wait(timeout=5)
        times = tuple(range(market.from_ms, market.to_ms, market.step_ms))
        return MultiIndicatorSeriesResult(
            time_ms=times,
            values_by_period={
                period: tuple(str(period + index) for index, _ in enumerate(times))
                for period in periods
            },
            plan_hash="multi-plan",
            market_data_hash="market",
        )


class FakeMarketData:
    def __init__(self) -> None:
        self.bounds_calls: list[tuple[str, str]] = []

    def health(self) -> bool:
        return True

    def get_bounds(self, *, ticker: str, timeframe: str) -> StreamBounds:
        self.bounds_calls.append((ticker, timeframe))
        return StreamBounds(
            ticker=ticker,
            timeframe=timeframe,
            earliest_open_time_ms=0,
            latest_open_time_ms=FULL_TO_MS - STEP_MS,
            stream_state="ready",
        )


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def make_client(
    tmp_path: Path,
    strategy: FakeStrategyEngine,
    market: FakeMarketData | None = None,
) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(
                settings,
                strategy,
                market or FakeMarketData(),
                ArtifactStore(tmp_path),
            ),
        )
    )


def request_params(period: int = 200) -> dict[str, str | int]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "period": period,
        "from": REQUEST_FROM_MS,
        "to": REQUEST_TO_MS,
    }


def wait_until_full(client: TestClient) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get("/api/market/ema-window", params=request_params()).json()
        if body["coverage"]["calculation_origin_ms"] == 0:  # type: ignore[index]
            return body
        time.sleep(0.01)
    raise AssertionError("full EMA entry was not published")


def test_cold_request_builds_one_three_ema_preview_with_warmup(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    market = FakeMarketData()
    client = make_client(tmp_path, strategy, market)
    try:
        response = client.get("/api/market/ema-window", params=request_params())
        assert response.status_code == 200
        assert strategy.full_started.wait(timeout=1)
        preview_calls = [call for call in strategy.multi_calls if call[0].from_ms != 0]
        assert len(preview_calls) == 1
        preview_range, periods = preview_calls[0]
        assert periods == (200, 500, 1000)
        assert (preview_range.from_ms, preview_range.to_ms) == (
            PREVIEW_FROM_MS,
            REQUEST_TO_MS,
        )
        assert market.bounds_calls == [("BTCUSDT.P", "5m")]
        assert response.json()["coverage"] == {
            "requested_from_ms": REQUEST_FROM_MS,
            "requested_to_ms": REQUEST_TO_MS,
            "actual_from_ms": REQUEST_FROM_MS,
            "actual_to_ms": REQUEST_TO_MS,
            "calculation_origin_ms": PREVIEW_FROM_MS,
            "coverage_to_ms": REQUEST_TO_MS,
            "cache_hit": False,
            "truncated": False,
        }
    finally:
        strategy.release_full.set()


def test_stack_periods_reuse_preview_and_preview_never_expands(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    try:
        assert client.get("/api/market/ema-window", params=request_params(200)).status_code == 200
        for period in (500, 1000):
            response = client.get("/api/market/ema-window", params=request_params(period))
            assert response.status_code == 200
            assert response.json()["coverage"]["cache_hit"] is True

        outside = request_params(500)
        outside["from"] = 0
        outside["to"] = STEP_MS
        response = client.get("/api/market/ema-window", params=outside)
        assert response.status_code == 200
        assert response.json()["points"] == []
        assert response.json()["coverage"]["truncated"] is True
        assert response.json()["coverage"]["cache_hit"] is False
        assert len(strategy.multi_calls) == 2  # one full build and one preview
    finally:
        strategy.release_full.set()


def test_full_entry_atomically_replaces_preview_and_serves_earlier_windows(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    assert client.get("/api/market/ema-window", params=request_params()).status_code == 200
    strategy.release_full.set()
    full = wait_until_full(client)
    assert full["coverage"]["cache_hit"] is True  # type: ignore[index]
    assert full["coverage"]["coverage_to_ms"] == FULL_TO_MS  # type: ignore[index]

    earlier = request_params(1000)
    earlier["from"] = STEP_MS
    earlier["to"] = 3 * STEP_MS
    response = client.get("/api/market/ema-window", params=earlier)
    assert response.status_code == 200
    assert len(response.json()["points"]) == 2
    assert response.json()["coverage"]["calculation_origin_ms"] == 0
    assert response.json()["coverage"]["cache_hit"] is True
    assert len(strategy.multi_calls) == 2


def test_failed_full_build_keeps_preview_and_next_request_retries(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(block_full=False, fail_full_count=1)
    client = make_client(tmp_path, strategy)
    first = client.get("/api/market/ema-window", params=request_params(200))
    assert first.status_code == 200
    assert first.json()["coverage"]["calculation_origin_ms"] == PREVIEW_FROM_MS

    second = client.get("/api/market/ema-window", params=request_params(500))
    assert second.status_code == 200
    full = wait_until_full(client)
    assert full["coverage"]["calculation_origin_ms"] == 0  # type: ignore[index]
    full_calls = [call for call in strategy.multi_calls if call[0].from_ms == 0]
    preview_calls = [call for call in strategy.multi_calls if call[0].from_ms != 0]
    assert len(full_calls) == 2
    assert len(preview_calls) == 1


def test_concurrent_stack_requests_share_one_preview_and_one_full_build() -> None:
    strategy = FakeStrategyEngine(block_preview=True)
    use_case = GetEmaWindow(strategy, FakeMarketData())

    def execute(period: int):
        return use_case.execute(
            symbol="BTCUSDT",
            timeframe="5m",
            period=period,
            from_ms=REQUEST_FROM_MS,
            to_ms=REQUEST_TO_MS,
            origin_policy="canonical",
        )

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(execute, period) for period in (200, 500, 1000)]
            assert strategy.preview_started.wait(timeout=1)
            strategy.release_preview.set()
            results = [future.result(timeout=2) for future in futures]
        assert sorted(result.coverage.cache_hit for result in results) == [False, True, True]
        full_calls = [call for call in strategy.multi_calls if call[0].from_ms == 0]
        preview_calls = [call for call in strategy.multi_calls if call[0].from_ms != 0]
        assert len(full_calls) == 1
        assert len(preview_calls) == 1
    finally:
        strategy.release_preview.set()
        strategy.release_full.set()


def test_non_stack_period_is_an_uncached_one_off_preview(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    params = request_params(20)
    first = client.get("/api/market/ema-window", params=params)
    second = client.get("/api/market/ema-window", params=params)
    assert first.status_code == second.status_code == 200
    assert first.json()["coverage"]["cache_hit"] is False
    assert second.json()["coverage"]["cache_hit"] is False
    assert len(strategy.single_calls) == 2
    assert strategy.multi_calls == []


def test_ema_window_rejects_unsupported_origin_policy(tmp_path: Path) -> None:
    response = make_client(tmp_path, FakeStrategyEngine()).get(
        "/api/market/ema-window",
        params={**request_params(), "origin_policy": "window"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
