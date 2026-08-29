"""I5.A corrective pass regression test
(`compact-strategy-evaluation-boundary-v1`).

Proves `scripts/decode_historical_execution_projection.py --drive-loop` validates a
decoded projection against an INDEPENDENTLY fetched `MarketFrame`'s own
`market`/`market_data_hash`/candle count -- not the projection's own
self-reported values (which would validate the projection against
itself and could never fail). `HttpMarketDataClient` is monkeypatched
to return a fixed, known `MarketFrame` so this test needs no real
Market Data Service.
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from research_service.adapters.http.market_data_client import HttpMarketDataClient
from research_service.domain.contracts import Candle, MarketFrame, MarketRange
from research_service.domain.errors import UpstreamServiceError

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "decode_historical_execution_projection.py"
)


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("decode_historical_execution_projection", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_script_module()

_MARKET = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000 * 3)
_REAL_HASH = "real-market-hash"


def _real_candles(count: int = 3) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            open_time_ms=i * 300_000,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for i in range(count)
    )


def _patch_market_data_client(monkeypatch: pytest.MonkeyPatch, market_frame: MarketFrame) -> None:
    def fake_init(self: HttpMarketDataClient, base_url: str, timeout_seconds: float = 60.0) -> None:
        pass

    def fake_read_range(self: HttpMarketDataClient, market: MarketRange) -> MarketFrame:
        return market_frame

    def fake_close(self: HttpMarketDataClient) -> None:
        pass

    monkeypatch.setattr(HttpMarketDataClient, "__init__", fake_init)
    monkeypatch.setattr(HttpMarketDataClient, "read_range", fake_read_range)
    monkeypatch.setattr(HttpMarketDataClient, "close", fake_close)


def _projection_body(*, market_data_hash: str, bar_count: int) -> dict[str, Any]:
    return {
        "contract_version": "strategy_evaluation_execution.v2",
        "strategy_id": "ema_pullback",
        "config_hash": "cfg",
        "market": {
            "ticker": "BTCUSDT.P",
            "base_timeframe": "5m",
            "from_ms": 0,
            "to_ms": 300_000 * bar_count,
            "bar_count": bar_count,
            "market_data_hash": market_data_hash,
        },
        "entry_opportunities": [],
        "signal_exit_events": {
            "long": {"aligned": [], "countertrend": [], "neutral": []},
            "short": {"aligned": [], "countertrend": [], "neutral": []},
        },
        "warnings": [],
    }


def _write_projection(tmp_path: Path, body: dict[str, Any]) -> Path:
    path = tmp_path / "projection.json"
    path.write_text(json.dumps(body))
    return path


def _run_main(argv: list[str]) -> int:
    return int(_MODULE.main(argv))


def test_drive_loop_succeeds_when_projection_matches_the_real_market_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market_frame = MarketFrame(market=_MARKET, candles=_real_candles(3), market_data_hash=_REAL_HASH)
    _patch_market_data_client(monkeypatch, market_frame)
    projection_path = _write_projection(tmp_path, _projection_body(market_data_hash=_REAL_HASH, bar_count=3))

    exit_code = _run_main(
        [
            "--projection",
            str(projection_path),
            "--expected-ticker",
            "BTCUSDT.P",
            "--expected-timeframe",
            "5m",
            "--expected-from-ms",
            "0",
            "--expected-to-ms",
            str(300_000 * 3),
            "--drive-loop",
        ]
    )
    assert exit_code == 0


def test_drive_loop_fails_closed_on_market_data_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market_frame = MarketFrame(market=_MARKET, candles=_real_candles(3), market_data_hash=_REAL_HASH)
    _patch_market_data_client(monkeypatch, market_frame)
    # Projection self-reports a DIFFERENT hash than the real MarketFrame --
    # before the fix, alignment was checked against this same self-reported
    # value, so this case could never fail.
    projection_path = _write_projection(
        tmp_path, _projection_body(market_data_hash="wrong-hash", bar_count=3)
    )

    with pytest.raises(UpstreamServiceError):
        _run_main(
            [
                "--projection",
                str(projection_path),
                "--expected-ticker",
                "BTCUSDT.P",
                "--expected-timeframe",
                "5m",
                "--expected-from-ms",
                "0",
                "--expected-to-ms",
                str(300_000 * 3),
                "--drive-loop",
            ]
        )


def test_drive_loop_fails_closed_on_bar_count_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market_frame = MarketFrame(market=_MARKET, candles=_real_candles(3), market_data_hash=_REAL_HASH)
    _patch_market_data_client(monkeypatch, market_frame)
    # Projection self-reports bar_count=3 (matching itself) but the real
    # MarketFrame only has 3 candles too -- so instead mismatch by giving
    # the projection a bar_count that disagrees with the real MarketFrame's
    # actual candle count (still 3, matching its own market.to_ms), while
    # the real MarketFrame is patched to a different candle count below.
    projection_path = _write_projection(
        tmp_path, _projection_body(market_data_hash=_REAL_HASH, bar_count=3)
    )
    # Patch read_range to return a frame whose candle count differs from
    # the projection's self-reported bar_count (5 real candles vs. 3).
    five_bar_market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000 * 5)
    mismatched_frame = MarketFrame(
        market=five_bar_market, candles=_real_candles(5), market_data_hash=_REAL_HASH
    )
    _patch_market_data_client(monkeypatch, mismatched_frame)

    with pytest.raises(UpstreamServiceError):
        _run_main(
            [
                "--projection",
                str(projection_path),
                "--expected-ticker",
                "BTCUSDT.P",
                "--expected-timeframe",
                "5m",
                "--expected-from-ms",
                "0",
                "--expected-to-ms",
                str(300_000 * 3),
                "--drive-loop",
            ]
        )


def test_without_drive_loop_does_not_touch_market_data_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression fence: the non-drive-loop decode-only path must not
    # construct an HttpMarketDataClient at all.
    def fail_init(self: HttpMarketDataClient, base_url: str, timeout_seconds: float = 60.0) -> None:
        raise AssertionError("HttpMarketDataClient must not be constructed without --drive-loop")

    monkeypatch.setattr(HttpMarketDataClient, "__init__", fail_init)
    projection_path = _write_projection(tmp_path, _projection_body(market_data_hash=_REAL_HASH, bar_count=3))

    exit_code = _run_main(
        [
            "--projection",
            str(projection_path),
            "--expected-ticker",
            "BTCUSDT.P",
            "--expected-timeframe",
            "5m",
            "--expected-from-ms",
            "0",
            "--expected-to-ms",
            str(300_000 * 3),
        ]
    )
    assert exit_code == 0
