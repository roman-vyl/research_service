"""Phase 4 policy: forbidden paths, core deps, no vectorbt inside data_engine."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_paths_absent_for_phase4() -> None:
    forbidden = [
        "data_engine/indicators",
        "data_engine/realtime",
        "data_engine/adapters",
        "data_engine/service/api.py",
        "data_engine/service/scheduler.py",
    ]
    assert [path for path in forbidden if (ROOT / path).exists()] == []


def test_forbidden_dependencies_not_in_core_for_phase4() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"]).lower()
    forbidden = ["pandas", "numpy", "vectorbt", "fastapi", "apscheduler", "pyarrow", "hypothesis"]
    assert [dependency for dependency in forbidden if dependency in dependencies] == []


def test_data_engine_has_no_vectorbt_imports() -> None:
    engine_root = ROOT / "data_engine"
    offenders: list[str] = []
    for path in sorted(engine_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "vectorbt" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"vectorbt must not appear in data_engine: {offenders}"
