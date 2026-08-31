#!/usr/bin/env python3
"""Mechanical, fail-closed supervisor for BBB AutoResearch sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_VERSION = "bbb_autoresearch_state.v1"
ITERATION_VERSION = "bbb_autoresearch_iteration.v1"
JOURNAL_VERSION = "bbb_autoresearch_journal.v1"
TERMINAL_STATUSES = frozenset({"hard_stopped", "completed", "cancelled"})
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REPO_ROOT = Path(__file__).resolve().parents[1]


class ContractError(ValueError):
    """A persisted AutoResearch document does not satisfy its v1 contract."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_session_id(value: str) -> str:
    if not SESSION_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise ContractError(
            "session id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        )
    return value


def session_dir(session_id: str, repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / "var" / "autoresearch" / validate_session_id(session_id)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def _require_string(value: dict[str, Any], key: str, *, nullable: bool = False) -> None:
    item = value.get(key)
    if nullable and item is None:
        return
    if not isinstance(item, str) or not item.strip():
        raise ContractError(f"{key} must be a non-empty string")


def _require_list(value: dict[str, Any], key: str) -> None:
    if not isinstance(value.get(key), list):
        raise ContractError(f"{key} must be an array")


def validate_state(state: dict[str, Any]) -> None:
    if state.get("contract_version") != STATE_VERSION:
        raise ContractError(f"contract_version must be {STATE_VERSION}")
    validate_session_id(str(state.get("session_id", "")))
    for key in (
        "research_program",
        "skill_path",
        "baseline_git_sha",
        "created_at",
        "updated_at",
        "phase",
    ):
        _require_string(state, key)
    if state.get("status") not in {
        "initialized",
        "running",
        "hard_stopped",
        "completed",
        "cancelled",
    }:
        raise ContractError("invalid state status")
    if not isinstance(state.get("iteration"), int) or state["iteration"] < 0:
        raise ContractError("iteration must be a non-negative integer")
    for key in (
        "competing_explanations",
        "findings",
        "structural_dimensions_known",
        "tested_ranges",
        "observed_response_shapes",
        "promising_regions",
        "rejected_regions",
        "unresolved_questions",
        "completed_phases",
    ):
        _require_list(state, key)
    for key in (
        "current_hypothesis",
        "side_asymmetry",
        "thinning_risk",
        "temporal_regime_concentration_concern",
        "validation_status",
        "next_discriminating_question",
        "stop_reason",
    ):
        item = state.get(key)
        if item is not None and not isinstance(item, str):
            raise ContractError(f"{key} must be a string or null")
    for key in ("next_experiment", "last_iteration_result"):
        item = state.get(key)
        if item is not None and not isinstance(item, dict):
            raise ContractError(f"{key} must be an object or null")
    budgets = state.get("budgets")
    if not isinstance(budgets, dict):
        raise ContractError("budgets must be an object")
    for key in (
        "max_iterations",
        "max_wall_clock_seconds",
        "max_candidates_per_iteration",
    ):
        item = budgets.get(key)
        if item is not None and (not isinstance(item, int) or item < 1):
            raise ContractError(f"budgets.{key} must be a positive integer or null")
    failures = budgets.get("max_consecutive_agent_failures")
    if not isinstance(failures, int) or failures < 1:
        raise ContractError("budgets.max_consecutive_agent_failures must be positive")


def validate_state_transition(previous: dict[str, Any], current: dict[str, Any]) -> None:
    """Reject identity/iteration rewinds and all transitions out of terminal state."""

    validate_state(previous)
    validate_state(current)
    if previous["session_id"] != current["session_id"]:
        raise ContractError("session_id is immutable")
    if previous["baseline_git_sha"] != current["baseline_git_sha"]:
        raise ContractError("baseline_git_sha is immutable")
    if current["iteration"] < previous["iteration"]:
        raise ContractError("iteration cannot move backwards")
    if previous["status"] in TERMINAL_STATUSES and current != previous:
        raise ContractError("terminal session state cannot transition")


def validate_iteration_result(result: dict[str, Any], state: dict[str, Any]) -> None:
    if result.get("contract_version") != ITERATION_VERSION:
        raise ContractError(f"contract_version must be {ITERATION_VERSION}")
    if result.get("session_id") != state["session_id"]:
        raise ContractError("iteration result session_id differs from state")
    expected = state["iteration"] + 1
    if result.get("iteration_id") != expected:
        raise ContractError(f"iteration_id must be {expected}")
    status = result.get("status")
    if status not in {"completed", "hard_stop", "failed"}:
        raise ContractError("invalid iteration status")
    for key in (
        "phase",
        "hypothesis",
        "market_property_proxy",
        "conclusion",
        "next_discriminating_question",
    ):
        _require_string(result, key)
    for key in ("experiment", "execution_result", "observed_response", "side_interpretation"):
        if not isinstance(result.get(key), dict):
            raise ContractError(f"{key} must be an object")
    _require_list(result, "confounders")
    experiment = result["experiment"]
    if experiment.get("kind") not in {"batch", "artifact_diagnostic", "none"}:
        raise ContractError("experiment.kind is invalid")
    candidate_ids = experiment.get("candidate_ids", [])
    if not isinstance(candidate_ids, list) or any(not isinstance(item, str) for item in candidate_ids):
        raise ContractError("experiment.candidate_ids must be an array of strings")
    count = experiment.get("candidate_count", 0)
    if not isinstance(count, int) or count < 0 or count != len(candidate_ids):
        raise ContractError("experiment.candidate_count must match candidate_ids")
    execution = result["execution_result"]
    for key in ("completed_candidates", "failed_candidates"):
        if not isinstance(execution.get(key), int) or execution[key] < 0:
            raise ContractError(f"execution_result.{key} must be non-negative")
    run_ids = execution.get("run_ids")
    if not isinstance(run_ids, list) or any(not isinstance(item, str) for item in run_ids):
        raise ContractError("execution_result.run_ids must be an array of strings")
    hard_reason = result.get("hard_stop_reason")
    if status == "hard_stop" and (not isinstance(hard_reason, str) or not hard_reason.strip()):
        raise ContractError("hard_stop result requires hard_stop_reason")
    if status != "hard_stop" and hard_reason is not None:
        raise ContractError("hard_stop_reason is only valid for hard_stop")
    proposed = result.get("proposed_next_experiment")
    if proposed is not None and not isinstance(proposed, dict):
        raise ContractError("proposed_next_experiment must be an object or null")
    if experiment["kind"] == "batch":
        if not isinstance(experiment.get("experiment_id"), str) or not experiment["experiment_id"]:
            raise ContractError("batch experiment requires experiment_id")
        if count < 1:
            raise ContractError("batch experiment requires at least one candidate")
        artifact_path = execution.get("batch_artifact_path")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise ContractError("batch execution requires batch_artifact_path")
        artifact = Path(artifact_path)
        required = ("request.json", "summary.json", "manifest.json")
        if not artifact.is_dir() or any(not (artifact / name).is_file() for name in required):
            raise ContractError("batch artifact path is not a canonical persisted batch bundle")
        if len(run_ids) != execution["completed_candidates"]:
            raise ContractError("run_ids must match completed_candidates")
        if not isinstance(execution.get("market_data_hash"), str):
            raise ContractError("batch execution requires market_data_hash")
    candidate_budget = state["budgets"].get("max_candidates_per_iteration")
    if candidate_budget is not None and count > candidate_budget:
        raise ContractError("candidate count exceeds session budget")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def append_journal(path: Path, event: dict[str, Any]) -> None:
    if event.get("contract_version") != JOURNAL_VERSION:
        raise ContractError(f"journal contract_version must be {JOURNAL_VERSION}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
    )
    return completed.stdout


def git_sha(repo_root: Path = REPO_ROOT) -> str:
    return _git(repo_root, "rev-parse", "HEAD").strip()


def git_branch(repo_root: Path = REPO_ROOT) -> str:
    return _git(repo_root, "branch", "--show-current").strip()


def repository_violations(repo_root: Path, allowed_runtime_root: Path) -> list[str]:
    """Return dirty tracked paths and untracked paths outside one session root."""

    paths: set[str] = set()
    for args in (("diff", "--name-only"), ("diff", "--cached", "--name-only")):
        paths.update(line for line in _git(repo_root, *args).splitlines() if line)
    paths.update(
        line
        for line in _git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines()
        if line
    )
    allowed = allowed_runtime_root.resolve()
    violations: list[str] = []
    for relative in sorted(paths):
        candidate = (repo_root / relative).resolve()
        if candidate != allowed and allowed not in candidate.parents:
            violations.append(relative)
    return violations


def render_prompt(state: dict[str, Any], root: Path, iteration_root: Path) -> str:
    template = (root / "autoresearch" / "prompts" / "iteration.md").read_text(
        encoding="utf-8"
    )
    values = {
        "program_path": root / "autoresearch" / "program.md",
        "skill_path": root / state["skill_path"],
        "state_path": session_dir(state["session_id"], root) / "state.json",
        "journal_path": session_dir(state["session_id"], root) / "journal.jsonl",
        "iteration_dir": iteration_root,
        "result_path": iteration_root / "iteration_result.json",
        "iteration_id": state["iteration"] + 1,
    }
    rendered = template.format(**{key: str(value) for key, value in values.items()})
    if state["iteration"] == 0:
        bootstrap = (root / "autoresearch" / "prompts" / "bootstrap.md").read_text(
            encoding="utf-8"
        )
        return f"{bootstrap}\n\n{rendered}"
    return rendered


def _command_args(template: str, values: dict[str, str]) -> list[str]:
    try:
        args = [item.format(**values) for item in shlex.split(template)]
    except (ValueError, KeyError) as exc:
        raise ContractError(f"invalid agent command template: {exc}") from exc
    if not args:
        raise ContractError("agent command is empty")
    return args


def _read_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"contract_version": "bbb_autoresearch_supervisor_metadata.v1", "attempts": []}
    metadata = load_json(path)
    if not isinstance(metadata.get("attempts"), list):
        raise ContractError("supervisor metadata attempts must be an array")
    return metadata


def _write_hard_stop(state_path: Path, state: dict[str, Any], reason: str) -> None:
    stopped = dict(state)
    stopped.update(status="hard_stopped", stop_reason=reason, updated_at=utc_now())
    validate_state(stopped)
    validate_state_transition(state, stopped)
    atomic_write_json(state_path, stopped)


def _journal_has_iteration(path: Path, session_id: str, iteration_id: int) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(f"journal contains malformed JSON: {exc}") from exc
        if item.get("session_id") == session_id and item.get("iteration_id") == iteration_id:
            return True
    return False


def _budget_reason(state: dict[str, Any], max_iterations: int | None) -> str | None:
    configured = state["budgets"].get("max_iterations")
    limits = [item for item in (configured, max_iterations) if item is not None]
    if limits and state["iteration"] >= min(limits):
        return "iteration budget exhausted"
    wall = state["budgets"].get("max_wall_clock_seconds")
    if wall is not None:
        created = datetime.fromisoformat(state["created_at"])
        if (datetime.now(UTC) - created).total_seconds() >= wall:
            return "wall-clock budget exhausted"
    return None


def _journal_event(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    experiment = result["experiment"]
    execution = result["execution_result"]
    return {
        "contract_version": JOURNAL_VERSION,
        "session_id": state["session_id"],
        "iteration_id": result["iteration_id"],
        "timestamp": utc_now(),
        "baseline_git_sha": state["baseline_git_sha"],
        "research_phase": result["phase"],
        "hypothesis": result["hypothesis"],
        "competing_explanation": state["competing_explanations"],
        "experiment_id": experiment.get("experiment_id"),
        "candidate_ids": experiment.get("candidate_ids", []),
        "window_policy": experiment.get("window_policy"),
        "strategy_context": experiment.get("strategy_context"),
        "parameter_axes": experiment.get("axes", []),
        "execution_accounting_assumptions": experiment.get(
            "execution_accounting_assumptions"
        ),
        "batch_artifact_path": execution.get("batch_artifact_path"),
        "run_ids": execution.get("run_ids", []),
        "market_data_hash": execution.get("market_data_hash"),
        "outcome_classification": result["observed_response"].get("topology"),
        "conclusion": result["conclusion"],
        "next_question": result["next_discriminating_question"],
    }


def _advance_state(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    observed = result["observed_response"]
    side = result["side_interpretation"]
    proposed = result.get("proposed_next_experiment")
    status = result["status"]
    if status == "hard_stop":
        next_status = "hard_stopped"
    elif status == "failed":
        next_status = "hard_stopped"
    elif proposed is None:
        next_status = "completed"
    else:
        next_status = "running"
    updated = dict(state)
    updated.update(
        status=next_status,
        updated_at=utc_now(),
        iteration=result["iteration_id"],
        phase=result["phase"],
        current_hypothesis=result["hypothesis"],
        findings=[*state["findings"], {"iteration_id": result["iteration_id"], "conclusion": result["conclusion"]}],
        structural_dimensions_known=list(
            dict.fromkeys(
                [*state["structural_dimensions_known"], *observed.get("structural_dimensions", [])]
            )
        ),
        tested_ranges=[*state["tested_ranges"], *observed.get("tested_ranges", [])],
        observed_response_shapes=[
            *state["observed_response_shapes"],
            {"iteration_id": result["iteration_id"], "topology": observed.get("topology")},
        ],
        promising_regions=[*state["promising_regions"], *observed.get("promising_regions", [])],
        rejected_regions=[*state["rejected_regions"], *observed.get("rejected_regions", [])],
        unresolved_questions=[
            *state["unresolved_questions"], result["next_discriminating_question"]
        ],
        side_asymmetry=side.get("aggregate"),
        thinning_risk="; ".join(result["confounders"]) or None,
        temporal_regime_concentration_concern=observed.get(
            "temporal_regime_concentration_concern"
        ),
        next_discriminating_question=result["next_discriminating_question"],
        next_experiment=proposed,
        last_iteration_result={
            "iteration_id": result["iteration_id"],
            "status": result["status"],
            "conclusion": result["conclusion"],
        },
        stop_reason=(result.get("hard_stop_reason") if next_status == "hard_stopped" else None),
    )
    validate_state(updated)
    validate_state_transition(state, updated)
    return updated


def run_supervisor(
    *,
    session_id: str,
    agent_command: str,
    repo_root: Path = REPO_ROOT,
    max_iterations: int | None = None,
    max_agent_failures: int | None = None,
    agent_timeout_seconds: int | None = None,
) -> int:
    root = session_dir(session_id, repo_root)
    state_path = root / "state.json"
    journal_path = root / "journal.jsonl"
    while True:
        state = load_json(state_path)
        validate_state(state)
        if state["status"] in TERMINAL_STATUSES:
            return 0
        if (root / "cancel.requested.json").exists():
            cancelled = dict(state)
            cancelled.update(status="cancelled", stop_reason="operator cancellation", updated_at=utc_now())
            validate_state(cancelled)
            atomic_write_json(state_path, cancelled)
            return 0
        reason = _budget_reason(state, max_iterations)
        if reason:
            _write_hard_stop(state_path, state, reason)
            return 2
        if git_sha(repo_root) != state["baseline_git_sha"]:
            _write_hard_stop(state_path, state, "repository HEAD differs from session baseline")
            return 2
        violations = repository_violations(repo_root, root)
        if violations:
            _write_hard_stop(
                state_path, state, f"unauthorized repository changes before iteration: {violations}"
            )
            return 2

        iteration_id = state["iteration"] + 1
        iteration_root = root / "iterations" / f"{iteration_id:04d}"
        iteration_root.mkdir(parents=True, exist_ok=True)
        result_path = iteration_root / "iteration_result.json"
        if _journal_has_iteration(journal_path, state["session_id"], iteration_id):
            if not result_path.is_file():
                _write_hard_stop(
                    state_path,
                    state,
                    "journal contains uncommitted iteration but its result file is missing",
                )
                return 2
            recovered = load_json(result_path)
            validate_iteration_result(recovered, state)
            atomic_write_json(state_path, _advance_state(state, recovered))
            continue
        prompt = render_prompt(state, repo_root, iteration_root)
        (iteration_root / "prompt.txt").write_text(prompt, encoding="utf-8")
        metadata_path = iteration_root / "supervisor_metadata.json"
        metadata = _read_metadata(metadata_path)
        attempts = metadata["attempts"]
        failure_limit = (
            max_agent_failures
            if max_agent_failures is not None
            else state["budgets"]["max_consecutive_agent_failures"]
        )

        accepted = False
        while len(attempts) < failure_limit:
            retry = len(attempts)
            result_path.unlink(missing_ok=True)
            stdout_path = iteration_root / ("stdout.log" if retry == 0 else f"stdout.retry-{retry:02d}.log")
            stderr_path = iteration_root / ("stderr.log" if retry == 0 else f"stderr.retry-{retry:02d}.log")
            started_at = utc_now()
            started = time.monotonic()
            before_sha = git_sha(repo_root)
            before_branch = git_branch(repo_root)
            values = {
                "prompt_file": str(iteration_root / "prompt.txt"),
                "result_file": str(result_path),
                "session_dir": str(root),
                "iteration_dir": str(iteration_root),
                "iteration_id": str(iteration_id),
            }
            args = _command_args(agent_command, values)
            exit_code: int | None = None
            failure: str | None = None
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                try:
                    completed = subprocess.run(
                        args,
                        cwd=repo_root,
                        input=prompt.encode("utf-8"),
                        stdout=stdout,
                        stderr=stderr,
                        timeout=agent_timeout_seconds,
                        check=False,
                    )
                    exit_code = completed.returncode
                except subprocess.TimeoutExpired:
                    failure = "agent timeout"
                    exit_code = 124
                except OSError as exc:
                    failure = f"agent spawn failed: {exc}"
                    exit_code = 127
            violations = repository_violations(repo_root, root)
            after_sha = git_sha(repo_root)
            after_branch = git_branch(repo_root)
            if after_sha != before_sha:
                violations.append(f"HEAD changed: {before_sha} -> {after_sha}")
            if after_branch != before_branch:
                violations.append(f"branch changed: {before_branch} -> {after_branch}")
            if violations:
                failure = f"unauthorized repository changes: {violations}"
            result: dict[str, Any] | None = None
            if failure is None and exit_code == 0:
                try:
                    result = load_json(result_path)
                    validate_iteration_result(result, state)
                except ContractError as exc:
                    failure = f"invalid iteration result: {exc}"
            elif failure is None:
                failure = f"agent exited with code {exit_code}"
            attempt = {
                "retry_index": retry,
                "started_at": started_at,
                "ended_at": utc_now(),
                "duration_seconds": round(time.monotonic() - started, 6),
                "exit_code": exit_code,
                "git_sha_before": before_sha,
                "git_sha_after": after_sha,
                "mutation_guard": {"ok": not violations, "violations": violations},
                "failure": failure,
            }
            attempts.append(attempt)
            metadata["attempts"] = attempts
            atomic_write_json(metadata_path, metadata)
            if violations:
                _write_hard_stop(state_path, state, failure or "repository mutation")
                return 2
            if failure is not None:
                continue
            assert result is not None
            event = _journal_event(state, result)
            append_journal(journal_path, event)
            updated = _advance_state(state, result)
            atomic_write_json(state_path, updated)
            accepted = True
            if updated["status"] in TERMINAL_STATUSES:
                return 0 if updated["status"] in {"completed", "cancelled"} else 2
            break
        if not accepted:
            _write_hard_stop(
                state_path,
                state,
                f"repeated agent/process failure: {len(attempts)} attempts",
            )
            return 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--agent-command", default=os.getenv("BBB_AUTORESEARCH_AGENT_COMMAND"))
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--max-agent-failures", type=int)
    parser.add_argument("--agent-timeout-seconds", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.agent_command:
        raise SystemExit("provide --agent-command or BBB_AUTORESEARCH_AGENT_COMMAND")
    return run_supervisor(
        session_id=args.session,
        agent_command=args.agent_command,
        max_iterations=args.max_iterations,
        max_agent_failures=args.max_agent_failures,
        agent_timeout_seconds=args.agent_timeout_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
