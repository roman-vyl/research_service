from pathlib import Path

from typer.testing import CliRunner

from data_engine.contracts import Candle, TimeWindow
from data_engine.contracts.fix_report import FixReport
from data_engine.contracts.gap import Gap
from data_engine.service import cli
from data_engine.service.cli import app
from data_engine.store import Db


def _report(status: str = "ok") -> FixReport:
    return FixReport(
        symbol="BTCUSDT",
        timeframe="1h",
        window=TimeWindow(0, 7_200_000),
        status=status,
        gaps_before=[],
        gaps_after=[],
        fetched_rows=2,
        written_rows=2,
        invalid_ohlc_rows=0,
        fresh=True,
        diagnostics=[],
    )


class _DiscoveryFetcher:
    def __init__(self, first_open_time_ms: int | None = None) -> None:
        self.first_open_time_ms = first_open_time_ms

    def fetch_candles(self, request):
        if self.first_open_time_ms is None:
            return []
        if request.window.start_ms <= self.first_open_time_ms < request.window.end_ms:
            return [Candle("BTCUSDT", "1h", self.first_open_time_ms, 1, 2, 0.5, 1.5, 10)]
        return []


def test_fix_rejects_unsupported_timeframe(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["fix", "--symbol", "BTCUSDT", "--tf", "2h", "--db-path", str(tmp_path / "x.sqlite")],
    )
    assert result.exit_code != 0
    assert "unsupported" in (result.stdout + result.stderr).lower()


def test_fix_cli_builds_full_historical_window_and_delegates_to_fix_candles(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "fix.sqlite"
    calls = {}
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 500)
    monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000 + 123)
    monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=3_600_000))

    def _fake_fix(
        symbol,
        tf,
        window,
        db,
        fetcher,
        expected_latest_open_ms=None,
        max_fetch_candles_per_request=200,
    ):
        calls["symbol"] = symbol
        calls["tf"] = tf
        calls["window"] = window
        calls["expected_latest_open_ms"] = expected_latest_open_ms
        calls["max_fetch_candles_per_request"] = max_fetch_candles_per_request
        return _report("ok")

    monkeypatch.setattr(cli, "fix_candles", _fake_fix)
    result = CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert result.exit_code == 0
    assert calls["symbol"] == "BTCUSDT"
    assert calls["window"].start_ms == 3_600_000
    assert calls["window"].end_ms == 10_800_000
    assert calls["expected_latest_open_ms"] == 7_200_000
    assert calls["max_fetch_candles_per_request"] == cli.BYBIT_KLINE_LIMIT


def test_fix_cli_prints_report_fields(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "print.sqlite"
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 0)
    monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000)
    monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=0))
    monkeypatch.setattr(
        cli,
        "fix_candles",
        lambda *args, **kwargs: FixReport(
            symbol="BTCUSDT",
            timeframe="1h",
            window=TimeWindow(0, 10_800_000),
            status="incomplete",
            gaps_before=[Gap(0, 3_600_000)],
            gaps_after=[Gap(7_200_000, 10_800_000)],
            fetched_rows=1,
            written_rows=1,
            invalid_ohlc_rows=0,
            fresh=False,
            diagnostics=["missing latest closed candle"],
        ),
    )
    result = CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert "symbol: BTCUSDT" in result.stdout
    assert "timeframe: 1h" in result.stdout
    assert "from_ms: 0" in result.stdout
    assert "to_ms: 7200000" in result.stdout
    assert "gaps_before: 1" in result.stdout
    assert "gaps_after: 1" in result.stdout
    assert "fetched_rows: 1" in result.stdout
    assert "written_rows: 1" in result.stdout
    assert "invalid_ohlc_rows: 0" in result.stdout
    assert "fresh: false" in result.stdout
    assert "status: incomplete" in result.stdout
    assert "diagnostic: missing latest closed candle" in result.stdout


def test_fix_cli_exits_zero_on_ok(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "ok.sqlite"
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 0)
    monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000)
    monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=0))
    monkeypatch.setattr(cli, "fix_candles", lambda *args, **kwargs: _report("ok"))
    result = CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert result.exit_code == 0


def test_fix_cli_exits_nonzero_on_incomplete_invalid_or_error(tmp_path: Path, monkeypatch) -> None:
    for status in ("incomplete", "invalid", "error"):
        db_file = tmp_path / f"{status}.sqlite"
        monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 0)
        monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000)
        monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=0))
        monkeypatch.setattr(cli, "fix_candles", lambda *args, **kwargs: _report(status))
        result = CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
        assert result.exit_code == 1


def test_fix_cli_schema_mismatch_returns_error_without_fetch(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "broken.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.conn.execute("DROP TABLE meta;")
    db.conn.commit()
    called = {"fetcher": False}

    def _make_fetcher():
        called["fetcher"] = True
        return _DiscoveryFetcher(first_open_time_ms=0)

    monkeypatch.setattr(cli, "_make_fetcher", _make_fetcher)
    result = CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert result.exit_code == 1
    assert "status: error" in result.stdout
    assert called["fetcher"] is False


def test_fix_cli_uses_effective_from_ms_when_db_has_rows(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "hasrows.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.upsert([Candle("BTCUSDT", "1h", 3_600_000, 1, 2, 0.5, 1.5, 10)])
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 0)
    monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000)
    monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=0))
    captured = {}
    monkeypatch.setattr(
        cli,
        "fix_candles",
        lambda symbol, tf, window, db, fetcher, expected_latest_open_ms=None, max_fetch_candles_per_request=200: captured.setdefault("window", window)
        or _report("ok"),
    )
    CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert captured["window"].start_ms == 3_600_000


def test_fix_cli_discovers_first_available_candle_on_empty_db(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "discover.sqlite"
    monkeypatch.setattr(cli, "_resolve_launch_time", lambda db, symbol: 500)
    monkeypatch.setattr(cli, "_now_ms", lambda: 10_800_000 + 123)
    monkeypatch.setattr(cli, "_make_fetcher", lambda: _DiscoveryFetcher(first_open_time_ms=3_600_000))
    captured = {}
    monkeypatch.setattr(
        cli,
        "fix_candles",
        lambda symbol, tf, window, db, fetcher, expected_latest_open_ms=None, max_fetch_candles_per_request=200: captured.setdefault("window", window)
        or _report("ok"),
    )
    CliRunner().invoke(app, ["fix", "--symbol", "BTCUSDT", "--tf", "1h", "--db-path", str(db_file)])
    assert captured["window"].start_ms == 3_600_000
