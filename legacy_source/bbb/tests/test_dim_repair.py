from __future__ import annotations

from dataclasses import dataclass

from data_engine.contracts import Candle, FetchRequest, TimeWindow
from data_engine.engine.dim import fix_candles


@dataclass
class FakeDb:
    candles: list[Candle]

    def __post_init__(self) -> None:
        self.upsert_calls = 0
        self.quarantine_calls: list[dict] = []

    def range_get(self, symbol: str, tf: str, window: TimeWindow) -> list[Candle]:
        rows = [
            row
            for row in self.candles
            if row.symbol == symbol
            and row.timeframe == tf
            and window.start_ms <= row.open_time_ms < window.end_ms
        ]
        return sorted(rows, key=lambda row: row.open_time_ms)

    def upsert(self, rows: list[Candle]) -> int:
        self.upsert_calls += 1
        for row in rows:
            self.candles = [
                existing
                for existing in self.candles
                if not (
                    existing.symbol == row.symbol
                    and existing.timeframe == row.timeframe
                    and existing.open_time_ms == row.open_time_ms
                )
            ]
            self.candles.append(row)
        return len(rows)

    def put_quarantine(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
        reason: str,
        payload: str,
        created_at_ms: int,
    ) -> None:
        self.quarantine_calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "reason": reason,
                "payload": payload,
                "created_at_ms": created_at_ms,
            }
        )


class FakeFetcher:
    def __init__(self, responses: dict[tuple[int, int], list[Candle]] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or {}
        self.error = error
        self.calls: list[FetchRequest] = []

    def fetch_candles(self, request: FetchRequest) -> list[Candle]:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.responses.get((request.window.start_ms, request.window.end_ms), [])


def _candle(open_time_ms: int, *, o: float = 1.0, h: float = 2.0, l: float = 0.5, c: float = 1.5, v: float = 10.0) -> Candle:
    return Candle("BTCUSDT", "1h", open_time_ms, o, h, l, c, v)


def _candle_tf(tf: str, open_time_ms: int) -> Candle:
    return Candle("BTCUSDT", tf, open_time_ms, 1.0, 2.0, 0.5, 1.5, 10.0)


def test_fix_candles_does_not_touch_other_timeframe_for_same_symbol() -> None:
    db = FakeDb(
        candles=[
            _candle_tf("5m", 0),
            _candle_tf("5m", 600_000),
            _candle_tf("1h", 0),
            _candle_tf("1h", 3_600_000),
        ]
    )
    fetcher = FakeFetcher(responses={(300_000, 600_000): [_candle_tf("5m", 300_000)]})
    report = fix_candles("BTCUSDT", "5m", TimeWindow(0, 900_000), db, fetcher)
    assert report.status == "ok"
    one_h = sorted([c.open_time_ms for c in db.candles if c.timeframe == "1h"])
    assert one_h == [0, 3_600_000]


def test_fix_candles_complete_window_does_not_fetch() -> None:
    db = FakeDb(candles=[_candle(0), _candle(3_600_000)])
    fetcher = FakeFetcher()
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 7_200_000), db, fetcher)
    assert report.status == "ok"
    assert report.gaps_before == []
    assert report.fetched_rows == 0
    assert fetcher.calls == []


def test_fix_candles_empty_db_repairs_full_window_gap() -> None:
    window = TimeWindow(0, 7_200_000)
    db = FakeDb(candles=[])
    fetcher = FakeFetcher(responses={(0, 7_200_000): [_candle(0), _candle(3_600_000)]})
    report = fix_candles("BTCUSDT", "1h", window, db, fetcher)
    assert report.status == "ok"
    assert report.gaps_after == []
    assert report.written_rows == 2


def test_fix_candles_repairs_one_middle_gap() -> None:
    window = TimeWindow(0, 10_800_000)
    db = FakeDb(candles=[_candle(0), _candle(7_200_000)])
    fetcher = FakeFetcher(responses={(3_600_000, 7_200_000): [_candle(3_600_000)]})
    report = fix_candles("BTCUSDT", "1h", window, db, fetcher)
    assert report.status == "ok"
    assert len(fetcher.calls) == 1
    assert fetcher.calls[0].window.start_ms == 3_600_000
    assert report.gaps_after == []


def test_fix_candles_reports_incomplete_when_fetch_returns_empty() -> None:
    db = FakeDb(candles=[_candle(0), _candle(7_200_000)])
    fetcher = FakeFetcher()
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 10_800_000), db, fetcher)
    assert report.status == "incomplete"
    assert len(report.gaps_after) == 1
    assert db.quarantine_calls


def test_fix_candles_reports_error_when_fetcher_raises() -> None:
    db = FakeDb(candles=[_candle(0)])
    fetcher = FakeFetcher(error=RuntimeError("boom"))
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 7_200_000), db, fetcher)
    assert report.status == "error"
    assert "boom" in " ".join(report.diagnostics)
    assert db.quarantine_calls


def test_fix_candles_reports_invalid_ohlc_without_mutating_rows() -> None:
    invalid = _candle(0, o=2.0, h=1.0, l=0.5, c=1.5)
    db = FakeDb(candles=[invalid])
    fetcher = FakeFetcher()
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 3_600_000), db, fetcher)
    assert report.status == "invalid"
    assert report.invalid_ohlc_rows == 1
    assert db.candles[0] == invalid


def test_fix_candles_reports_incomplete_when_postflight_gaps_remain() -> None:
    db = FakeDb(candles=[_candle(0), _candle(10_800_000)])
    fetcher = FakeFetcher(responses={(3_600_000, 10_800_000): [_candle(7_200_000)]})
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 14_400_000), db, fetcher)
    assert report.status == "incomplete"
    assert report.gaps_after


def test_fix_candles_is_not_recursive() -> None:
    db = FakeDb(candles=[_candle(0), _candle(10_800_000)])
    fetcher = FakeFetcher()
    report = fix_candles("BTCUSDT", "1h", TimeWindow(0, 14_400_000), db, fetcher)
    assert report.status == "incomplete"
    assert len(fetcher.calls) == 1


def test_fix_candles_does_not_import_cli() -> None:
    assert "data_engine.service.cli" not in fix_candles.__globals__


def test_fix_candles_splits_large_gap_into_multiple_fetch_calls() -> None:
    step_ms = 3_600_000
    candles_count = 450
    window = TimeWindow(0, candles_count * step_ms)
    db = FakeDb(candles=[])

    class LimitedFetcher:
        def __init__(self) -> None:
            self.calls: list[FetchRequest] = []

        def fetch_candles(self, request: FetchRequest) -> list[Candle]:
            self.calls.append(request)
            candles_in_window = (request.window.end_ms - request.window.start_ms) // step_ms
            if candles_in_window > 200:
                raise RuntimeError("window exceeds 200 candles")
            rows: list[Candle] = []
            ts = request.window.start_ms
            while ts < request.window.end_ms:
                rows.append(_candle(ts))
                ts += step_ms
            return rows

    fetcher = LimitedFetcher()
    report = fix_candles(
        "BTCUSDT",
        "1h",
        window,
        db,
        fetcher,
        max_fetch_candles_per_request=200,
    )
    assert report.status == "ok"
    assert len(fetcher.calls) == 3
    assert report.gaps_after == []


def test_fix_candles_reports_incomplete_on_unexpected_fetch_rows() -> None:
    window = TimeWindow(0, 7_200_000)
    db = FakeDb(candles=[])

    class UnexpectedRowsFetcher:
        def __init__(self) -> None:
            self.calls: list[FetchRequest] = []

        def fetch_candles(self, request: FetchRequest) -> list[Candle]:
            self.calls.append(request)
            return [
                _candle(0),
                Candle("ETHUSDT", "1h", 0, 1, 2, 0.5, 1.5, 10),
                Candle("BTCUSDT", "4h", 0, 1, 2, 0.5, 1.5, 10),
                Candle("BTCUSDT", "1h", 9_999_999, 1, 2, 0.5, 1.5, 10),
            ]

    fetcher = UnexpectedRowsFetcher()
    report = fix_candles("BTCUSDT", "1h", window, db, fetcher)
    assert report.status != "ok"
    assert any("unexpected rows" in diagnostic for diagnostic in report.diagnostics)
