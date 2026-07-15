"""HTTP integration tests for market window endpoints (Phase 4)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from data_engine.contracts import Candle
from data_engine.store.db import Db
from research_api.contracts.chart import CHART_OVERLAY_EMA_KIND
from research_api.main import app
from research_api.services.chart_ema_cache import reset_chart_ema_cache_for_tests


STEP_MS = 300_000


def _seed_candles(db_path, *, count: int = 6, start: int = 1_714_550_400_000) -> tuple[str, str, int, int]:
    db = Db(db_path)
    db.apply_ddl()
    rows = [
        Candle(
            "BTCUSDT",
            "5m",
            start + i * STEP_MS,
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
    to_ms = start + count * STEP_MS
    return "BTCUSDT", "5m", from_ms, to_ms


def _patch_db(monkeypatch: pytest.MonkeyPatch, db_file) -> TestClient:
    import research_api.services.market_reader as reader

    class _Settings:
        db_path = db_file

    monkeypatch.setattr(reader, "Settings", lambda: _Settings())
    reset_chart_ema_cache_for_tests()
    return TestClient(app)


def test_http_candles_window_shape(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    client = _patch_db(monkeypatch, db_file)

    resp = client.get(
        "/api/market/candles-window",
        params={"symbol": symbol, "timeframe": tf, "from": from_ms, "to": to_ms},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "candles" in body
    assert "coverage" in body
    assert len(body["candles"]) == 6
    cov = body["coverage"]
    assert cov["requested_from_ms"] == from_ms
    assert cov["requested_to_ms"] == to_ms
    assert cov["actual_from_ms"] == from_ms
    assert cov["actual_to_ms"] == to_ms
    assert cov["truncated"] is False


def test_http_ema_window_shape(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    client = _patch_db(monkeypatch, db_file)

    resp = client.get(
        "/api/market/ema-window",
        params={
            "symbol": symbol,
            "timeframe": tf,
            "period": 2,
            "from": from_ms,
            "to": to_ms,
            "origin_policy": "canonical",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body
    assert "coverage" in body
    assert len(body["points"]) == 6
    assert body["points"][0]["kind"] == CHART_OVERLAY_EMA_KIND
    cov = body["coverage"]
    assert cov["requested_from_ms"] == from_ms
    assert cov["requested_to_ms"] == to_ms
    assert cov["calculation_origin_ms"] == from_ms
    assert cov["coverage_to_ms"] == to_ms
    assert cov["cache_hit"] is False
    assert cov["truncated"] is False


def test_http_ema_window_cache_hit_on_second_request(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    client = _patch_db(monkeypatch, db_file)
    params = {
        "symbol": symbol,
        "timeframe": tf,
        "period": 2,
        "from": from_ms,
        "to": to_ms,
    }

    first = client.get("/api/market/ema-window", params=params)
    assert first.status_code == 200
    assert first.json()["coverage"]["cache_hit"] is False

    second = client.get("/api/market/ema-window", params=params)
    assert second.status_code == 200
    assert second.json()["coverage"]["cache_hit"] is True


def test_http_window_endpoints_subset_not_full_seed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file, count=6)
    subset_to = from_ms + 2 * STEP_MS
    client = _patch_db(monkeypatch, db_file)

    candles = client.get(
        "/api/market/candles-window",
        params={"symbol": symbol, "timeframe": tf, "from": from_ms, "to": subset_to},
    )
    assert candles.status_code == 200
    assert len(candles.json()["candles"]) == 2
    assert candles.json()["coverage"]["actual_to_ms"] == subset_to

    ema = client.get(
        "/api/market/ema-window",
        params={
            "symbol": symbol,
            "timeframe": tf,
            "period": 2,
            "from": from_ms,
            "to": subset_to,
        },
    )
    assert ema.status_code == 200
    ema_body = ema.json()
    assert len(ema_body["points"]) == 2
    assert ema_body["coverage"]["requested_to_ms"] == subset_to
    assert ema_body["coverage"]["coverage_to_ms"] == subset_to
    assert ema_body["coverage"]["actual_to_ms"] == subset_to


def test_http_window_endpoints_validation_400(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    client = _patch_db(monkeypatch, db_file)

    bad_range = client.get(
        "/api/market/candles-window",
        params={"symbol": symbol, "timeframe": tf, "from": to_ms, "to": from_ms},
    )
    assert bad_range.status_code == 400

    bad_policy = client.get(
        "/api/market/ema-window",
        params={
            "symbol": symbol,
            "timeframe": tf,
            "period": 2,
            "from": from_ms,
            "to": to_ms,
            "origin_policy": "display",
        },
    )
    assert bad_policy.status_code == 400


def test_http_window_endpoints_missing_db_503(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.sqlite"
    client = _patch_db(monkeypatch, missing)

    candles = client.get(
        "/api/market/candles-window",
        params={"symbol": "BTCUSDT", "timeframe": "5m", "from": 0, "to": STEP_MS},
    )
    assert candles.status_code == 503

    ema = client.get(
        "/api/market/ema-window",
        params={
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "period": 2,
            "from": 0,
            "to": STEP_MS,
        },
    )
    assert ema.status_code == 503
