import tomllib
from pathlib import Path

from data_engine.store.ddl import DDL_STATEMENTS


ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_paths_absent_for_phase2() -> None:
    forbidden = [
        "data_engine/indicators",
        "data_engine/realtime",
        "data_engine/adapters",
        "data_engine/service/api.py",
        "data_engine/service/scheduler.py",
    ]

    assert [path for path in forbidden if (ROOT / path).exists()] == []


def test_forbidden_dependencies_absent_for_phase2() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"]).lower()
    forbidden = ["pandas", "numpy", "vectorbt", "fastapi", "apscheduler", "pyarrow"]

    assert [dependency for dependency in forbidden if dependency in dependencies] == []


def test_phase2_does_not_extend_phase1_ddl() -> None:
    ddl = "\n".join(DDL_STATEMENTS)

    assert "PRIMARY KEY (symbol, timeframe, open_time_ms)" in ddl
    assert "retry_count" not in ddl
    assert "source" not in ddl
    assert "CREATE TABLE IF NOT EXISTS indicators" not in ddl
