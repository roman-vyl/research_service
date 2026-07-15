from pathlib import Path

from data_engine.contracts import Candle, TimeWindow
from data_engine.store import Db


def _db(tmp_path: Path) -> Db:
    db = Db(tmp_path / "store.sqlite")
    db.apply_ddl()
    return db


def _candle(symbol: str, tf: str, open_time_ms: int, close: float = 1.0) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=tf,
        open_time_ms=open_time_ms,
        open=1.0,
        high=2.0,
        low=0.5,
        close=close,
        volume=10.0,
    )


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    first = _candle("BTCUSDT", "1h", 0, close=1.0)
    updated = _candle("BTCUSDT", "1h", 0, close=2.0)

    assert db.upsert([first]) == 1
    assert db.upsert([updated]) == 1

    rows = db.range_get("BTCUSDT", "1h", TimeWindow(0, 3_600_000))
    assert len(rows) == 1
    assert rows[0].close == 2.0


def test_max_open_time_ms_empty_and_non_empty(tmp_path: Path) -> None:
    db = _db(tmp_path)

    assert db.max_open_time_ms("BTCUSDT", "1h") is None

    db.upsert(
        [
            _candle("BTCUSDT", "1h", 0),
            _candle("BTCUSDT", "1h", 3_600_000),
            _candle("ETHUSDT", "1h", 7_200_000),
            _candle("BTCUSDT", "5m", 10_800_000),
        ]
    )

    assert db.max_open_time_ms("BTCUSDT", "1h") == 3_600_000


def test_min_open_time_ms_empty_and_non_empty(tmp_path: Path) -> None:
    db = _db(tmp_path)

    assert db.min_open_time_ms("BTCUSDT", "1h") is None

    db.upsert(
        [
            _candle("BTCUSDT", "1h", 3_600_000),
            _candle("BTCUSDT", "1h", 7_200_000),
            _candle("ETHUSDT", "1h", 0),
            _candle("BTCUSDT", "5m", 0),
        ]
    )

    assert db.min_open_time_ms("BTCUSDT", "1h") == 3_600_000


def test_range_get_uses_half_open_window_and_returns_asc(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.upsert(
        [
            _candle("BTCUSDT", "1h", 7_200_000),
            _candle("BTCUSDT", "1h", 0),
            _candle("BTCUSDT", "1h", 3_600_000),
            _candle("BTCUSDT", "5m", 3_600_000),
            _candle("ETHUSDT", "1h", 3_600_000),
        ]
    )

    rows = db.range_get("BTCUSDT", "1h", TimeWindow(3_600_000, 7_200_000))

    assert [row.open_time_ms for row in rows] == [3_600_000]


def test_same_symbol_independent_timeframes(tmp_path: Path) -> None:
    db_file = tmp_path / "multi_tf.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert(
        [
            _candle("BTCUSDT", "5m", 0),
            _candle("BTCUSDT", "5m", 300_000),
            _candle("BTCUSDT", "1h", 0),
        ]
    )
    assert db.count_candles("BTCUSDT", "5m", TimeWindow(0, 600_000)) == 2
    assert db.count_candles("BTCUSDT", "1h", TimeWindow(0, 3_600_000)) == 1
    assert db.max_open_time_ms("BTCUSDT", "5m") == 300_000
    assert db.max_open_time_ms("BTCUSDT", "1h") == 0
    summary_5m = db.candle_summary("BTCUSDT", "5m")
    assert summary_5m["count"] == 2
    assert summary_5m["min_open_time_ms"] == 0
    assert summary_5m["max_open_time_ms"] == 300_000


def test_count_candles_filters_symbol_and_tf(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.upsert(
        [
            _candle("BTCUSDT", "1h", 0),
            _candle("BTCUSDT", "5m", 0),
            _candle("ETHUSDT", "1h", 0),
        ]
    )

    assert db.count_candles("BTCUSDT", "1h", TimeWindow(0, 3_600_000)) == 1


def test_launch_time_meta_roundtrip(tmp_path: Path) -> None:
    db = _db(tmp_path)

    assert db.get_launch_time_ms("BTCUSDT") is None

    db.set_launch_time_ms("BTCUSDT", 123)

    assert db.get_launch_time_ms("BTCUSDT") == 123
