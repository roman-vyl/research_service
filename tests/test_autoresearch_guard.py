from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from autoresearch_supervisor import repository_violations  # noqa: E402


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/evaluator.py").write_text("fixed = True\n")
    (tmp_path / "autoresearch").mkdir()
    (tmp_path / "autoresearch/program.md").write_text("immutable\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    session = tmp_path / "var/autoresearch/s1"
    session.mkdir(parents=True)
    return tmp_path, session


def test_session_runtime_changes_are_allowed(tmp_path: Path) -> None:
    repo, session = _repo(tmp_path)
    (session / "result.json").write_text("{}")
    assert repository_violations(repo, session) == []


def test_tracked_production_and_infrastructure_changes_are_rejected(tmp_path: Path) -> None:
    repo, session = _repo(tmp_path)
    (repo / "src/evaluator.py").write_text("fixed = False\n")
    (repo / "autoresearch/program.md").write_text("mutable\n")
    assert repository_violations(repo, session) == [
        "autoresearch/program.md",
        "src/evaluator.py",
    ]


def test_untracked_file_and_unrelated_openspec_change_are_rejected(tmp_path: Path) -> None:
    repo, session = _repo(tmp_path)
    (repo / "scratch.txt").write_text("x")
    path = repo / "openspec/changes/unrelated"
    path.mkdir(parents=True)
    (path / "proposal.md").write_text("x")
    assert repository_violations(repo, session) == [
        "openspec/changes/unrelated/proposal.md",
        "scratch.txt",
    ]


def test_staged_change_is_rejected(tmp_path: Path) -> None:
    repo, session = _repo(tmp_path)
    (repo / "src/evaluator.py").write_text("fixed = False\n")
    subprocess.run(["git", "add", "src/evaluator.py"], cwd=repo, check=True)
    assert repository_violations(repo, session) == ["src/evaluator.py"]
