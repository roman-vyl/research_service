from pathlib import Path
import sqlite3

from typer.testing import CliRunner

from data_engine.store import Db
from data_engine.service.cli import app


def test_status_creates_db_and_prints_expected_block(tmp_path: Path) -> None:
    db_file = tmp_path / "status.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["status", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert db_file.exists()
    output = result.stdout
    assert f"db_path: {db_file}" in output
    assert "schema_version: 1" in output
    assert "schema_meta: 1" in output
    assert "candles: 0" in output
    assert "meta: 0" in output
    assert "quarantine: 0" in output
    assert "contract: ok" in output


def test_status_symbol_tf_pair_shows_span(tmp_path: Path) -> None:
    db_file = tmp_path / "pair.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    from data_engine.contracts import Candle

    db.upsert(
        [
            Candle("BTCUSDT", "1h", 0, 1, 2, 0.5, 1.5, 10),
            Candle("BTCUSDT", "1h", 3_600_000, 1, 2, 0.5, 1.5, 10),
        ]
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["status", "--db-path", str(db_file), "--symbol", "BTCUSDT", "--tf", "1h"],
    )
    assert result.exit_code == 0
    assert "pair: BTCUSDT 1h" in result.stdout
    assert "pair_candles: 2" in result.stdout
    assert "pair_min_open_time_ms: 0" in result.stdout
    assert "pair_max_open_time_ms: 3600000" in result.stdout


def test_status_rejects_lone_symbol_without_tf(tmp_path: Path) -> None:
    db_file = tmp_path / "lone.sqlite"
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db-path", str(db_file), "--symbol", "BTCUSDT"])
    assert result.exit_code != 0


def test_status_reports_schema_mismatch_for_existing_broken_db(tmp_path: Path) -> None:
    db_file = tmp_path / "broken.sqlite"
    db = Db(db_file)
    db.apply_ddl()

    with sqlite3.connect(db_file) as conn:
        conn.execute("DROP TABLE meta;")
        conn.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert "contract: schema_mismatch" in result.stdout
