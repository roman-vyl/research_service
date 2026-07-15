"""Research API BFF — market candles and EMA.

Requires: ``pip install -e ".[dev,workbench-api]"``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from research_api.contracts.chart import ChartBar
from research_api.main import app
from research_api.contracts.chart import CHART_OVERLAY_EMA_KIND
from research_api.services.indicators import compute_chart_overlay_ema
from research_api.services.market_reader import (
    candle_to_chart_bar,
    exclusive_end_for_report_to,
    fetch_chart_bars,
    fetch_chart_market_bundle,
    fetch_ema_points,
    resolve_exclusive_to_ms,
)
from research_api.services.market_params import MarketParamError
from data_engine.contracts import Candle
from data_engine.store.db import Db


def _seed_candles(db_path, *, count: int = 5, step_ms: int = 300_000) -> tuple[str, str, int, int]:
    db = Db(db_path)
    db.apply_ddl()
    start = 1_714_550_400_000
    rows = [
        Candle(
            "BTCUSDT",
            "5m",
            start + i * step_ms,
            100.0 + i,
            101.0 + i,
            99.0 + i,
            100.5 + i,
            10.0 + i,
        )
        for i in range(count)
    ]
    db.upsert(rows)
    from_ms = start
    to_ms = start + count * step_ms
    return "BTCUSDT", "5m", from_ms, to_ms


def test_candle_to_chart_bar_time_seconds() -> None:
    bar = candle_to_chart_bar(
        Candle("BTCUSDT", "5m", 1_714_550_400_000, 1, 2, 0.5, 1.5, 3),
    )
    assert bar.time == 1_714_550_400


def test_fetch_chart_bars_and_ema(tmp_path) -> None:
    symbol, tf, from_ms, to_ms = _seed_candles(tmp_path / "market.sqlite")
    bars = fetch_chart_bars(
        symbol=symbol,
        timeframe=tf,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=tmp_path / "market.sqlite",
    )
    assert len(bars) == 5
    assert bars[0].time == from_ms // 1000

    ema = fetch_ema_points(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=tmp_path / "market.sqlite",
    )
    assert len(ema) == 5
    assert ema[0].time == bars[0].time


def test_resolve_exclusive_to_ms_uses_timeframe_ms() -> None:
    to_open = 1_714_550_400_000
    assert resolve_exclusive_to_ms(
        to_ms=None,
        to_open_time_ms=to_open,
        timeframe="5m",
    ) == exclusive_end_for_report_to(to_open_time_ms=to_open, timeframe="5m")
    assert resolve_exclusive_to_ms(to_ms=100, to_open_time_ms=None, timeframe="5m") == 100
    with pytest.raises(MarketParamError):
        resolve_exclusive_to_ms(to_ms=1, to_open_time_ms=2, timeframe="5m")


def test_http_candles_to_open_time_ms(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.market_reader as reader

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    last_open = to_ms - 300_000

    class _Settings:
        db_path = db_file

    monkeypatch.setattr(reader, "Settings", lambda: _Settings())

    client = TestClient(app)
    via_open = client.get(
        "/api/market/candles",
        params={"symbol": symbol, "timeframe": tf, "from": from_ms, "to_open_time_ms": last_open},
    )
    assert via_open.status_code == 200
    assert len(via_open.json()) == len(
        client.get(
            "/api/market/candles",
            params={"symbol": symbol, "timeframe": tf, "from": from_ms, "to": to_ms},
        ).json()
    )


def test_chart_overlay_ema_first_point_equals_first_close() -> None:
    """Documents window-local seeding (no warmup before ``from``)."""

    bars = [
        ChartBar(time=1, open=1, high=1, low=1, close=10, volume=1),
        ChartBar(time=2, open=1, high=1, low=1, close=20, volume=1),
    ]
    ema = compute_chart_overlay_ema(bars, period=2)
    assert ema[0].kind == CHART_OVERLAY_EMA_KIND
    assert ema[0].value == 10.0
    assert ema[1].value == pytest.approx((2 / 3) * 20 + (1 / 3) * 10)


def test_chart_overlay_ema_window_narrowing_changes_values() -> None:
    """EMA(2) on a sub-window is not the tail of EMA(2) on the full window."""

    bars = [
        ChartBar(time=i, open=1, high=1, low=1, close=float(c), volume=1)
        for i, c in enumerate([10.0, 20.0, 30.0], start=1)
    ]
    full = compute_chart_overlay_ema(bars, period=2)
    narrow = compute_chart_overlay_ema(bars[1:], period=2)
    assert narrow[0].value == 20.0
    assert narrow[0].value != full[1].value


def test_fetch_chart_market_bundle_single_read(tmp_path) -> None:
    symbol, tf, from_ms, to_ms = _seed_candles(tmp_path / "market.sqlite")
    bundle = fetch_chart_market_bundle(
        symbol=symbol,
        timeframe=tf,
        from_ms=from_ms,
        to_ms=to_ms,
        ema_fast=2,
        ema_anchor=3,
        ema_slow=4,
        db_path=tmp_path / "market.sqlite",
    )
    assert len(bundle.candles) == 5
    assert len(bundle.ema_overlays) == 3
    assert [o.role for o in bundle.ema_overlays] == ["fast", "anchor", "slow"]
    assert bundle.ema_overlays[0].points[0].kind == CHART_OVERLAY_EMA_KIND


def test_fetch_chart_market_bundle_rejects_invalid_stack_order() -> None:
    with pytest.raises(ValueError, match="fast < anchor < slow"):
        fetch_chart_market_bundle(
            symbol="BTCUSDT",
            timeframe="5m",
            from_ms=0,
            to_ms=1,
            ema_fast=500,
            ema_anchor=200,
            ema_slow=1000,
        )


def test_http_chart_bundle_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.market_reader as reader

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    last_open = to_ms - 300_000

    class _Settings:
        db_path = db_file

    monkeypatch.setattr(reader, "Settings", lambda: _Settings())

    client = TestClient(app)
    bundle = client.get(
        "/api/market/chart-bundle",
        params={
            "symbol": symbol,
            "timeframe": tf,
            "from": from_ms,
            "to_open_time_ms": last_open,
            "ema_fast": 2,
            "ema_anchor": 3,
            "ema_slow": 4,
        },
    )
    assert bundle.status_code == 200
    body = bundle.json()
    assert len(body["candles"]) == 5
    assert len(body["ema_overlays"]) == 3
    assert {o["role"] for o in body["ema_overlays"]} == {"fast", "anchor", "slow"}


def test_http_market_endpoints(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.market_reader as reader

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)

    class _Settings:
        db_path = db_file

    monkeypatch.setattr(reader, "Settings", lambda: _Settings())

    client = TestClient(app)
    candles = client.get(
        "/api/market/candles",
        params={"symbol": symbol, "timeframe": tf, "from": from_ms, "to": to_ms},
    )
    assert candles.status_code == 200
    assert len(candles.json()) == 5

    ema = client.get(
        "/api/market/indicators/ema",
        params={
            "symbol": symbol,
            "timeframe": tf,
            "period": 2,
            "from": from_ms,
            "to": to_ms,
        },
    )
    assert ema.status_code == 200
    assert len(ema.json()) == 5

    bad = client.get(
        "/api/market/candles",
        params={"symbol": symbol, "timeframe": tf, "from": to_ms, "to": from_ms},
    )
    assert bad.status_code == 400


def test_http_missing_db_returns_503(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.market_reader as reader

    missing = tmp_path / "missing.sqlite"

    class _Settings:
        db_path = missing

    monkeypatch.setattr(reader, "Settings", lambda: _Settings())

    client = TestClient(app)
    resp = client.get(
        "/api/market/candles",
        params={"symbol": "BTCUSDT", "timeframe": "5m", "from": 0, "to": 300_000},
    )
    assert resp.status_code == 503
