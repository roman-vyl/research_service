import sqlite3
from pathlib import Path

from data_engine.store import Db


def test_health_ok_on_fresh_schema(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    db.apply_ddl()

    health = db.health()

    assert health["contract"] == "ok"
    assert health["schema_version"] == 1
    assert health["schema_meta"] == 1
    assert health["candles"] == 0
    assert health["meta"] == 0
    assert health["quarantine"] == 0


def test_health_schema_mismatch_when_table_missing(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    db.apply_ddl()

    with sqlite3.connect(db_file) as conn:
        conn.execute("DROP TABLE meta;")
        conn.commit()

    db_after_drop = Db(db_file)
    health = db_after_drop.health()

    assert health["contract"] == "schema_mismatch"


def test_health_schema_mismatch_when_schema_version_is_unexpected(tmp_path: Path) -> None:
    db_file = tmp_path / "x.sqlite"
    db = Db(db_file)
    db.apply_ddl()

    with sqlite3.connect(db_file) as conn:
        conn.execute("UPDATE schema_meta SET value = '2' WHERE key = 'schema_version';")
        conn.commit()

    db_after_version_change = Db(db_file)
    health = db_after_version_change.health()

    assert health["contract"] == "schema_mismatch"
