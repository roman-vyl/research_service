import sqlite3
from pathlib import Path

from data_engine.store import Db
from data_engine.store.ddl import EXPECTED_TABLES


def test_apply_ddl_creates_expected_tables_and_index(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    db.apply_ddl()

    assert db_file.exists()

    with sqlite3.connect(db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%';"
            ).fetchall()
        }
        version_row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version';"
        ).fetchone()

    assert tables == set(EXPECTED_TABLES)
    assert "idx_candles_lookup" in indexes
    assert version_row == ("1",)


def test_apply_ddl_is_idempotent(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    db.apply_ddl()
    db.apply_ddl()

    with sqlite3.connect(db_file) as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_meta WHERE key='schema_version';").fetchone()[0]
    assert count == 1


def test_db_sets_journal_mode_wal(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    mode = db.conn.execute("PRAGMA journal_mode;").fetchone()[0]
    assert str(mode).lower() == "wal"
