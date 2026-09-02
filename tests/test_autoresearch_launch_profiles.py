from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


_FAKE_PYTHON_SCRIPT = """#!/bin/sh
printf 'engine=%s\\n' "$RESEARCH_STRATEGY_ENGINE_URL"
printf 'mds=%s\\n' "$RESEARCH_MARKET_DATA_URL"
printf 'artifacts=%s\\n' "$RESEARCH_ARTIFACTS_ROOT"
printf 'configs=%s\\n' "$RESEARCH_CONFIGS_ROOT"
printf 'research_service=%s\\n' "$BBB_AUTORESEARCH_RESEARCH_SERVICE_URL"
printf 'marker=%s\\n' "$PROVIDER_RUNTIME_MARKER"
for argument in "$@"; do printf 'arg=%s\\n' "$argument"; done
"""


def _fake_python(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "python"
    executable.write_text(_FAKE_PYTHON_SCRIPT, encoding="utf-8")
    executable.chmod(0o755)
    return bin_dir


def _fake_host_repo(tmp_path: Path, *, with_venv: bool = True) -> Path:
    fake_repo = tmp_path / "fake_repo"
    scripts_dir = fake_repo / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "scripts/autoresearch_run_host.sh",
        scripts_dir / "autoresearch_run_host.sh",
    )
    (scripts_dir / "autoresearch_supervisor.py").write_text("", encoding="utf-8")
    if with_venv:
        venv_bin = fake_repo / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text(_FAKE_PYTHON_SCRIPT, encoding="utf-8")
        python_path.chmod(0o755)
    return fake_repo


def _environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{_fake_python(tmp_path)}:{environment['PATH']}"
    environment["PROVIDER_RUNTIME_MARKER"] = "preserved"
    environment["RESEARCH_STRATEGY_ENGINE_URL"] = "http://wrong-engine"
    environment["RESEARCH_MARKET_DATA_URL"] = "http://wrong-mds"
    environment["BBB_AUTORESEARCH_RESEARCH_SERVICE_URL"] = "http://127.0.0.1:8000"
    return environment


def test_host_profile_sets_loopback_endpoints_and_forwards_arguments(tmp_path: Path) -> None:
    fake_repo = _fake_host_repo(tmp_path)
    environment = _environment(tmp_path)
    environment["RESEARCH_ARTIFACTS_ROOT"] = "/host/autoresearch"
    environment["RESEARCH_CONFIGS_ROOT"] = "/host/autoresearch/configs"

    result = subprocess.run(
        [
            str(fake_repo / "scripts/autoresearch_run_host.sh"),
            "--session",
            "smoke",
            "--max-iterations",
            "1",
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "engine=http://127.0.0.1:8090",
        "mds=http://127.0.0.1:8080",
        "artifacts=/host/autoresearch",
        "configs=/host/autoresearch/configs",
        "research_service=http://127.0.0.1:8000",
        "marker=preserved",
        f"arg={fake_repo / 'scripts/autoresearch_supervisor.py'}",
        "arg=--session",
        "arg=smoke",
        "arg=--max-iterations",
        "arg=1",
    ]


def test_host_profile_requires_repo_local_venv(tmp_path: Path) -> None:
    fake_repo = _fake_host_repo(tmp_path, with_venv=False)
    environment = _environment(tmp_path)
    environment["RESEARCH_ARTIFACTS_ROOT"] = "/host/autoresearch"
    environment["RESEARCH_CONFIGS_ROOT"] = "/host/autoresearch/configs"

    result = subprocess.run(
        [str(fake_repo / "scripts/autoresearch_run_host.sh"), "--session", "smoke"],
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 2
    assert str(fake_repo / ".venv/bin/python") in result.stderr
    assert "repo-local virtualenv" in result.stderr


def test_host_profile_requires_absolute_host_roots(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment["RESEARCH_ARTIFACTS_ROOT"] = "relative/artifacts"
    environment["RESEARCH_CONFIGS_ROOT"] = "/host/configs"

    result = subprocess.run(
        [str(REPO_ROOT / "scripts/autoresearch_run_host.sh"), "--session", "smoke"],
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 2
    assert "RESEARCH_ARTIFACTS_ROOT must be an absolute host path" in result.stderr


def test_host_profile_requires_research_service_base_url(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment["RESEARCH_ARTIFACTS_ROOT"] = "/host/autoresearch"
    environment["RESEARCH_CONFIGS_ROOT"] = "/host/autoresearch/configs"
    del environment["BBB_AUTORESEARCH_RESEARCH_SERVICE_URL"]

    result = subprocess.run(
        [str(REPO_ROOT / "scripts/autoresearch_run_host.sh"), "--session", "smoke"],
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "BBB_AUTORESEARCH_RESEARCH_SERVICE_URL" in result.stderr


def test_docker_profile_sets_service_dns_and_explicit_default_roots(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment.pop("RESEARCH_ARTIFACTS_ROOT", None)
    environment.pop("RESEARCH_CONFIGS_ROOT", None)

    result = subprocess.run(
        [str(REPO_ROOT / "scripts/autoresearch_run_docker.sh"), "--session", "smoke"],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "engine=http://strategy-engine:8080",
        "mds=http://market-data-service:8080",
        "artifacts=/data/runs",
        "configs=/data/configs",
        "research_service=http://research-service:8080",
        "marker=preserved",
        f"arg={REPO_ROOT / 'scripts/autoresearch_supervisor.py'}",
        "arg=--session",
        "arg=smoke",
    ]
