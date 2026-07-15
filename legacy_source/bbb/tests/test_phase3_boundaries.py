import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_paths_absent_for_phase3() -> None:
    forbidden = [
        "data_engine/indicators",
        "data_engine/realtime",
        "data_engine/adapters",
        "data_engine/service/api.py",
        "data_engine/service/scheduler.py",
    ]
    assert [path for path in forbidden if (ROOT / path).exists()] == []


def test_forbidden_dependencies_absent_for_phase3() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"]).lower()
    forbidden = ["pandas", "numpy", "vectorbt", "fastapi", "apscheduler", "pyarrow", "hypothesis"]
    assert [dependency for dependency in forbidden if dependency in dependencies] == []
