from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import autoresearch_supervisor as supervisor_module  # noqa: E402
from autoresearch_worker_profiles import resolve_worker_profile  # noqa: E402


@pytest.mark.parametrize(
    ("key", "runner", "model", "argv"),
    (
        (
            "claude-sonnet46",
            "claude-code",
            "claude-sonnet-4-6",
            (
                "claude",
                "--print",
                "--model",
                "claude-sonnet-4-6",
                "--permission-mode",
                "auto",
                "--permission-prompts",
                "none",
            ),
        ),
        (
            "codex-gpt56-sol",
            "codex",
            "gpt-5.6-sol",
            (
                "codex",
                "exec",
                "-C",
                ".",
                "-s",
                "workspace-write",
                "-m",
                "gpt-5.6-sol",
                "-",
            ),
        ),
        (
            "glm52-opencode",
            "opencode",
            "speshu/z-ai/glm-5.2",
            ("opencode", "run", "--auto", "-m", "speshu/z-ai/glm-5.2"),
        ),
        (
            "qwen35-local",
            "opencode",
            "ollama/qwen3.5:9b",
            ("opencode", "run", "--auto", "-m", "ollama/qwen3.5:9b"),
        ),
    ),
)
def test_required_worker_profiles_resolve_exact_argv(
    key: str, runner: str, model: str, argv: tuple[str, ...]
) -> None:
    profile = resolve_worker_profile(key)

    assert profile.runner == runner
    assert profile.model == model
    assert profile.argv == argv
    assert profile.provenance() == {
        "worker_profile": key,
        "runner": runner,
        "model": model,
    }


def test_unknown_worker_profile_fails_closed_with_allowed_keys() -> None:
    with pytest.raises(ValueError, match="unknown AutoResearch worker profile") as error:
        resolve_worker_profile("invented-runner")

    message = str(error.value)
    for key in ("claude-sonnet46", "codex-gpt56-sol", "glm52-opencode", "qwen35-local"):
        assert key in message


def test_controlled_cli_uses_resolved_worker_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.delenv("BBB_AUTORESEARCH_AGENT_COMMAND", raising=False)
    monkeypatch.setattr(
        supervisor_module,
        "validate_cli_launch_profile",
        lambda _settings: ("controlled-host-v1", "http://127.0.0.1:8000"),
    )
    monkeypatch.setattr(supervisor_module, "preflight_launch_services", lambda *_args: None)
    monkeypatch.setattr(supervisor_module.shutil, "which", lambda _executable: "/bin/fake")

    def fake_run_supervisor(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(supervisor_module, "run_supervisor", fake_run_supervisor)

    assert (
        supervisor_module.main(
            ["--session", "s1", "--worker", "glm52-opencode", "--max-iterations", "4"]
        )
        == 0
    )
    profile = resolve_worker_profile("glm52-opencode")
    assert captured["agent_command"] == profile.argv
    assert captured["worker_identity"] == profile.provenance()
    assert captured["max_iterations"] == 4


def test_controlled_cli_uses_resolved_qwen_local_worker_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.delenv("BBB_AUTORESEARCH_AGENT_COMMAND", raising=False)
    monkeypatch.setattr(
        supervisor_module,
        "validate_cli_launch_profile",
        lambda _settings: ("controlled-host-v1", "http://127.0.0.1:8000"),
    )
    monkeypatch.setattr(supervisor_module, "preflight_launch_services", lambda *_args: None)
    monkeypatch.setattr(supervisor_module.shutil, "which", lambda _executable: "/bin/fake")

    def fake_run_supervisor(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(supervisor_module, "run_supervisor", fake_run_supervisor)

    assert (
        supervisor_module.main(
            ["--session", "s1", "--worker", "qwen35-local", "--max-iterations", "4"]
        )
        == 0
    )
    profile = resolve_worker_profile("qwen35-local")
    assert captured["agent_command"] == profile.argv
    assert captured["worker_identity"] == profile.provenance()
    assert captured["max_iterations"] == 4


def test_raw_agent_command_cannot_override_worker_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BBB_AUTORESEARCH_AGENT_COMMAND", "malicious --override")
    monkeypatch.setattr(
        supervisor_module,
        "run_supervisor",
        lambda **_kwargs: pytest.fail("raw command must fail before supervisor execution"),
    )

    with pytest.raises(SystemExit, match="not supported.*--worker"):
        supervisor_module.main(["--session", "s1", "--worker", "glm52-opencode"])
