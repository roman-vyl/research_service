"""Deterministic provider-neutral worker profiles for BBB AutoResearch."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class WorkerProfile:
    key: str
    runner: str
    model: str
    argv: tuple[str, ...]

    def provenance(self) -> dict[str, str]:
        return {
            "worker_profile": self.key,
            "runner": self.runner,
            "model": self.model,
        }


_WORKER_PROFILES = MappingProxyType(
    {
        "claude-sonnet46": WorkerProfile(
            key="claude-sonnet46",
            runner="claude-code",
            model="claude-sonnet-4-6",
            argv=(
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
        "codex-gpt56-sol": WorkerProfile(
            key="codex-gpt56-sol",
            runner="codex",
            model="gpt-5.6-sol",
            argv=(
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
        "glm52-opencode": WorkerProfile(
            key="glm52-opencode",
            runner="opencode",
            model="speshu/z-ai/glm-5.2",
            argv=("opencode", "run", "--auto", "-m", "speshu/z-ai/glm-5.2"),
        ),
    }
)


def worker_profile_keys() -> tuple[str, ...]:
    return tuple(sorted(_WORKER_PROFILES))


def resolve_worker_profile(key: str) -> WorkerProfile:
    try:
        return _WORKER_PROFILES[key]
    except KeyError as exc:
        allowed = ", ".join(worker_profile_keys())
        raise ValueError(f"unknown AutoResearch worker profile {key!r}; allowed: {allowed}") from exc
