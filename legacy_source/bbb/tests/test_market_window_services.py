"""Market window services (Phase 3 — no router)."""

from __future__ import annotations

import pytest

from data_engine.contracts import Candle
from data_engine.store.db import Db
from research_api.contracts.chart import CHART_OVERLAY_EMA_KIND, ChartBar
from research_api.services.chart_ema_cache import ChartEmaCache, reset_chart_ema_cache_for_tests
from research_api.services.indicators import compute_chart_overlay_ema, extend_chart_overlay_ema
from research_api.services.market_reader import (
    fetch_candles_window,
    fetch_chart_market_bundle,
    fetch_ema_window,
)

pytestmark = pytest.mark.workbench_api

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


def test_fetch_candles_window_full_coverage(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)

    bundle = fetch_candles_window(
        symbol=symbol,
        timeframe=tf,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
    )
    assert len(bundle.candles) == 6
    assert bundle.coverage.truncated is False
    assert bundle.coverage.actual_from_ms == from_ms
    assert bundle.coverage.actual_to_ms == to_ms
    assert bundle.coverage.requested_from_ms == from_ms
    assert bundle.coverage.requested_to_ms == to_ms


def test_fetch_candles_window_before_data_edge(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    early_from = from_ms - STEP_MS * 2
    early_to = from_ms + STEP_MS

    bundle = fetch_candles_window(
        symbol=symbol,
        timeframe=tf,
        from_ms=early_from,
        to_ms=early_to,
        db_path=db_file,
    )
    assert len(bundle.candles) == 1
    assert bundle.coverage.truncated is True
    assert bundle.coverage.actual_from_ms == from_ms
    assert bundle.coverage.requested_from_ms == early_from


def test_fetch_candles_window_fully_beyond_data(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    beyond_from = to_ms + STEP_MS
    beyond_to = beyond_from + STEP_MS

    bundle = fetch_candles_window(
        symbol=symbol,
        timeframe=tf,
        from_ms=beyond_from,
        to_ms=beyond_to,
        db_path=db_file,
    )
    assert bundle.candles == []
    assert bundle.coverage.truncated is True
    assert bundle.coverage.actual_from_ms == bundle.coverage.actual_to_ms == beyond_from


def test_ema_window_first_request_cache_miss(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    cache = reset_chart_ema_cache_for_tests()

    bundle = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )
    assert len(bundle.points) == 6
    assert bundle.coverage.cache_hit is False
    assert bundle.coverage.calculation_origin_ms == from_ms
    assert bundle.coverage.coverage_to_ms == to_ms
    assert bundle.points[0].kind == CHART_OVERLAY_EMA_KIND


def test_ema_window_pure_slice_cache_hit(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    cache = reset_chart_ema_cache_for_tests()

    first = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )
    mid_from = from_ms + STEP_MS
    mid_to = to_ms - STEP_MS

    second = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=mid_from,
        to_ms=mid_to,
        db_path=db_file,
        cache=cache,
    )
    assert second.coverage.cache_hit is True
    assert len(second.points) == 4
    overlap = [p for p in first.points if mid_from <= p.time * 1000 < mid_to]
    assert [p.value for p in second.points] == [p.value for p in overlap]


def test_ema_window_extension_cache_miss(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file, count=6)
    cache = reset_chart_ema_cache_for_tests()
    partial_to = from_ms + 3 * STEP_MS

    first = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=partial_to,
        db_path=db_file,
        cache=cache,
    )
    assert first.coverage.cache_hit is False

    second = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )
    assert second.coverage.cache_hit is False
    assert second.coverage.coverage_to_ms == to_ms
    assert len(second.points) == 6
    assert second.points[2].value == pytest.approx(first.points[2].value)


def test_ema_window_matches_chart_bundle_at_same_bars(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    cache = reset_chart_ema_cache_for_tests()
    period = 2

    full_bundle = fetch_chart_market_bundle(
        symbol=symbol,
        timeframe=tf,
        from_ms=from_ms,
        to_ms=to_ms,
        ema_fast=period,
        ema_anchor=3,
        ema_slow=4,
        db_path=db_file,
    )
    fast_overlay = next(o for o in full_bundle.ema_overlays if o.role == "fast")

    window = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=period,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )
    assert len(window.points) == len(fast_overlay.points)
    for got, expected in zip(window.points, fast_overlay.points, strict=True):
        assert got.time == expected.time
        assert got.value == pytest.approx(expected.value)


def test_ema_window_fully_beyond_data_empty(tmp_path) -> None:
    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    cache = reset_chart_ema_cache_for_tests()
    beyond_from = to_ms + STEP_MS
    beyond_to = beyond_from + STEP_MS

    bundle = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=beyond_from,
        to_ms=beyond_to,
        db_path=db_file,
        cache=cache,
    )
    assert bundle.points == []
    assert bundle.coverage.truncated is True
    assert bundle.coverage.cache_hit is False
    assert bundle.coverage.actual_from_ms == bundle.coverage.actual_to_ms == beyond_from


def test_ema_cache_invalidates_on_market_data_identity(tmp_path) -> None:
    db_file_a = tmp_path / "a.sqlite"
    db_file_b = tmp_path / "b.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file_a, count=6)
    # Same time grid, different closes → distinct canonical series after cache miss.
    db = Db(db_file_b)
    db.apply_ddl()
    start = from_ms
    rows = [
        Candle(
            "BTCUSDT",
            "5m",
            start + i * STEP_MS,
            200.0 + i,
            201.0 + i,
            199.0 + i,
            200.5 + i,
            20.0 + i,
        )
        for i in range(6)
    ]
    db.upsert(rows)

    cache = ChartEmaCache()
    first = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file_a,
        cache=cache,
    )
    second = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file_b,
        cache=cache,
    )
    assert first.coverage.cache_hit is False
    assert second.coverage.cache_hit is False
    assert len(second.points) == len(first.points)
    assert first.points[0].value != second.points[0].value


def test_extend_chart_overlay_ema_continues_series() -> None:
    bars = [
        ChartBar(time=i, open=1, high=1, low=1, close=float(c), volume=1)
        for i, c in enumerate([10.0, 20.0, 30.0, 40.0], start=1)
    ]
    full = compute_chart_overlay_ema(bars, period=2)
    seed = compute_chart_overlay_ema(bars[:2], period=2)
    extended = extend_chart_overlay_ema(seed, bars[2:], period=2)
    assert [p.value for p in extended] == [p.value for p in full]


def test_ema_first_miss_single_chart_bars_read(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_api.services.chart_ema_cache as ema_cache_mod

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file, count=6)
    cache = reset_chart_ema_cache_for_tests()
    calls: list[tuple[int, int]] = []

    original = ema_cache_mod.fetch_chart_bars

    def _spy_fetch_chart_bars(**kwargs):
        calls.append((int(kwargs["from_ms"]), int(kwargs["to_ms"])))
        return original(**kwargs)

    monkeypatch.setattr(ema_cache_mod, "fetch_chart_bars", _spy_fetch_chart_bars)

    fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )

    assert calls == [(0, to_ms)]


def test_ema_extension_reads_append_range_only(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_api.services.chart_ema_cache as ema_cache_mod

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file, count=6)
    cache = reset_chart_ema_cache_for_tests()
    partial_to = from_ms + 3 * STEP_MS
    calls: list[tuple[int, int]] = []

    original = ema_cache_mod.fetch_chart_bars

    def _spy_fetch_chart_bars(**kwargs):
        calls.append((int(kwargs["from_ms"]), int(kwargs["to_ms"])))
        return original(**kwargs)

    monkeypatch.setattr(ema_cache_mod, "fetch_chart_bars", _spy_fetch_chart_bars)

    fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=partial_to,
        db_path=db_file,
        cache=cache,
    )
    calls.clear()

    fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )

    assert calls == [(partial_to, to_ms)]


def test_ema_pure_slice_does_not_touch_db(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_api.services.chart_ema_cache as ema_cache_mod

    db_file = tmp_path / "market.sqlite"
    symbol, tf, from_ms, to_ms = _seed_candles(db_file)
    cache = reset_chart_ema_cache_for_tests()

    fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms,
        to_ms=to_ms,
        db_path=db_file,
        cache=cache,
    )

    def _forbidden_fetch(**_kwargs):
        raise AssertionError("fetch_chart_bars must not run on pure cache slice")

    monkeypatch.setattr(ema_cache_mod, "fetch_chart_bars", _forbidden_fetch)

    second = fetch_ema_window(
        symbol=symbol,
        timeframe=tf,
        period=2,
        from_ms=from_ms + STEP_MS,
        to_ms=to_ms - STEP_MS,
        db_path=db_file,
        cache=cache,
    )
    assert second.coverage.cache_hit is True
