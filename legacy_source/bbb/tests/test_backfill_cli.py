import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from data_engine.contracts import Candle, FetchRequest
from data_engine.engine.time_grid import tf_ms
from data_engine.service import cli
from data_engine.service.cli import app
from data_engine.store import Db


class FakeFetcher:
    def __init__(
        self,
        *,
        drop_last: bool = False,
        empty: bool = False,
        leading_empty_chunks: int = 0,
        empty_after_data: bool = False,
    ) -> None:
        self.drop_last = drop_last
        self.empty = empty
        self.leading_empty_chunks = leading_empty_chunks
        self.empty_after_data = empty_after_data
        self._seen_data_chunk = False
        self.requests: list[FetchRequest] = []

    def fetch_candles(self, request: FetchRequest) -> list[Candle]:
        self.requests.append(request)
        if self.empty:
            return []
        if self.leading_empty_chunks > 0:
            self.leading_empty_chunks -= 1
            return []
        if self.empty_after_data and self._seen_data_chunk:
            return []

        rows: list[Candle] = []
        open_time_ms = request.window.start_ms
        step = tf_ms(request.timeframe)
        while open_time_ms < request.window.end_ms:
            rows.append(
                Candle(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    open_time_ms=open_time_ms,
                    open=1.0,
                    high=2.0,
                    low=0.5,
                    close=1.5,
                    volume=10.0,
                )
            )
            open_time_ms += step
        if self.drop_last and rows:
            rows.pop()
        if rows:
            self._seen_data_chunk = True
        return rows


def _patch_backfill(monkeypatch, fetcher: FakeFetcher, *, launch_time_ms: int = 0, now_ms: int = 10_800_000) -> None:
    monkeypatch.setattr(cli, "_make_fetcher", lambda: fetcher)
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: launch_time_ms)
    monkeypatch.setattr(cli, "_now_ms", lambda: now_ms)


def _invoke(db_file: Path) -> object:
    runner = CliRunner()
    return runner.invoke(app, ["backfill", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])


def test_backfill_non_1h_timeframe(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "tf5m.sqlite"
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=10_800_000)
    runner = CliRunner()
    result = runner.invoke(app, ["backfill", "--symbol", "BTCUSDT", "--tf", "5m", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert "timeframe: 5m" in result.stdout
    assert "status: ok" in result.stdout
    assert fetcher.requests[0].timeframe == "5m"


def test_backfill_rejects_unsupported_timeframe(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["backfill", "--symbol", "BTCUSDT", "--tf", "1m", "--db-path", str(tmp_path / "bad.sqlite")],
    )
    assert result.exit_code != 0
    assert "unsupported" in (result.stdout + result.stderr).lower()


def test_backfill_from_empty_db(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "empty.sqlite"
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "status: ok" in result.stdout
    assert "expected_count: 3" in result.stdout
    assert "actual_count: 3" in result.stdout


def test_backfill_existing_broken_db_is_not_auto_fixed(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "broken.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    with sqlite3.connect(db_file) as conn:
        conn.execute("DROP TABLE meta;")
        conn.commit()
    _patch_backfill(monkeypatch, FakeFetcher())

    result = _invoke(db_file)

    assert result.exit_code == 1
    assert "status: error" in result.stdout
    assert "schema_mismatch" in result.stdout
    with sqlite3.connect(db_file) as conn:
        meta = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta';"
        ).fetchone()
    assert meta is None


def test_backfill_resume_from_last_open_time(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "resume.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert([FakeFetcher().fetch_candles(FetchRequest("BTCUSDT", "1h", cli.TimeWindow(0, 7_200_000)))[-1]])
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=14_400_000)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert fetcher.requests[0].window.start_ms == 7_200_000


def test_backfill_idempotent_second_run(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "idempotent.sqlite"
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher)
    first = _invoke(db_file)

    second_fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, second_fetcher)
    second = _invoke(db_file)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "status: ok" in second.stdout
    assert second_fetcher.requests == []


def test_backfill_uses_full_history_window_for_completion_check(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "full-history.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert(
        [
            Candle("BTCUSDT", "1h", 0, 1, 2, 0.5, 1.5, 10),
            Candle("BTCUSDT", "1h", 3_600_000, 1, 2, 0.5, 1.5, 10),
        ]
    )
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=10_800_000)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "expected_count: 3" in result.stdout
    assert "actual_count: 3" in result.stdout


def test_backfill_reports_incomplete_when_counts_mismatch(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "incomplete.sqlite"
    fetcher = FakeFetcher(drop_last=True)
    _patch_backfill(monkeypatch, fetcher)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "status: incomplete" in result.stdout
    assert "expected_count: 3" in result.stdout
    assert "actual_count: 2" in result.stdout


def test_backfill_sets_error_when_no_candles_found_in_expected_range(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "empty-chunk.sqlite"
    fetcher = FakeFetcher(empty=True)
    _patch_backfill(monkeypatch, fetcher)

    result = _invoke(db_file)

    assert result.exit_code == 1
    assert "status: error" in result.stdout
    assert "no candles found in expected range" in result.stdout


def test_backfill_allows_leading_empty_chunk_and_advances_cursor(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "leading-empty.sqlite"
    fetcher = FakeFetcher(leading_empty_chunks=1)
    _patch_backfill(monkeypatch, fetcher, now_ms=3_600_000 * 250)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "status: ok" in result.stdout
    assert len(fetcher.requests) == 2
    assert fetcher.requests[0].window.start_ms == 0
    assert fetcher.requests[0].window.end_ms == 3_600_000 * 200
    assert fetcher.requests[1].window.start_ms == 3_600_000 * 200


def test_backfill_errors_on_empty_chunk_after_data_started(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "empty-after-data.sqlite"
    fetcher = FakeFetcher(empty_after_data=True)
    _patch_backfill(monkeypatch, fetcher, now_ms=3_600_000 * 250)

    result = _invoke(db_file)

    assert result.exit_code == 1
    assert "status: error" in result.stdout
    assert "empty fetch chunk" in result.stdout


def test_backfill_reports_from_ms_as_effective_from_ms(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "from-ms-effective.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert([Candle("BTCUSDT", "1h", 3_600_000, 1, 2, 0.5, 1.5, 10)])
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=10_800_000)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "from_ms: 3600000" in result.stdout


def test_backfill_chunks_fetch_windows(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "chunks.sqlite"
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=3_600_000 * 250)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert len(fetcher.requests) == 2
    assert fetcher.requests[0].window.end_ms - fetcher.requests[0].window.start_ms == 3_600_000 * 200


def test_backfill_resume_completion_uses_existing_min_open_time(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "resume-min.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert(
        [
            Candle("BTCUSDT", "1h", 3_600_000, 1, 2, 0.5, 1.5, 10),
            Candle("BTCUSDT", "1h", 10_800_000, 1, 2, 0.5, 1.5, 10),
        ]
    )
    fetcher = FakeFetcher()
    _patch_backfill(monkeypatch, fetcher, now_ms=14_400_000)

    result = _invoke(db_file)

    assert result.exit_code == 0
    assert "status: incomplete" in result.stdout
    assert "expected_count: 3" in result.stdout
    assert "actual_count: 2" in result.stdout
