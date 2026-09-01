#!/usr/bin/env python3
"""Mechanical, fail-closed supervisor for BBB AutoResearch sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from research_service.application.experiments import (
    BatchExperimentRequest,
    BatchExperimentResult,
)
from research_service.runtime.settings import Settings

from autoresearch_quality_contracts import (
    CANONICAL_METRIC_PATHS,
    PromotionBlocker,
    describe_stage_metric_role_contract,
    enforce_quality_policy,
    phase_binding,
    validate_assessment,
    validate_policy,
)

STATE_VERSION = "bbb_autoresearch_state.v1"
STATE_VERSION_V2 = "bbb_autoresearch_state.v2"
ITERATION_VERSION = "bbb_autoresearch_iteration.v1"
ITERATION_VERSION_V2 = "bbb_autoresearch_iteration.v2"
JOURNAL_VERSION = "bbb_autoresearch_journal.v1"
JOURNAL_VERSION_V2 = "bbb_autoresearch_journal.v2"
PLAN_VERSION = "bbb_autoresearch_execution_plan.v1"
RECEIPT_VERSION = "bbb_autoresearch_execution_receipt.v1"
CONTROL_VERSION = "bbb_autoresearch_iteration_control.v1"
TERMINAL_STATUSES = frozenset({"hard_stopped", "completed", "cancelled"})
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REPO_ROOT = Path(__file__).resolve().parents[1]

_STATE_KEYS = {
    "contract_version",
    "session_id",
    "research_program",
    "skill_path",
    "strategy_context",
    "status",
    "baseline_git_sha",
    "created_at",
    "updated_at",
    "iteration",
    "phase",
    "completed_phases",
    "current_hypothesis",
    "competing_explanations",
    "findings",
    "structural_dimensions_known",
    "tested_ranges",
    "observed_response_shapes",
    "promising_regions",
    "rejected_regions",
    "aggregate_interpretation",
    "long_interpretation",
    "short_interpretation",
    "side_asymmetry",
    "thinning_risk",
    "temporal_regime_concentration_concern",
    "other_confounders",
    "unresolved_questions",
    "validation_status",
    "next_discriminating_question",
    "next_experiment",
    "last_iteration_result",
    "budgets",
    "stop_reason",
}
_STATE_V2_KEYS = _STATE_KEYS | {
    "research_quality_policy",
    "active_stage_binding",
    "latest_quality_assessment",
    "promotion_history",
}
_ITERATION_KEYS = {
    "contract_version",
    "session_id",
    "iteration_id",
    "status",
    "phase",
    "hypothesis",
    "market_property_proxy",
    "experiment",
    "execution_result",
    "observed_response",
    "side_interpretation",
    "risk_assessment",
    "conclusion",
    "next_discriminating_question",
    "proposed_next_experiment",
    "hard_stop_reason",
}
_ITERATION_V2_KEYS = _ITERATION_KEYS | {"research_quality_assessment"}
_EXPERIMENT_KEYS = {
    "kind",
    "experiment_id",
    "axes",
    "candidate_ids",
    "candidate_count",
    "window_policy",
    "strategy_context",
    "execution_accounting_assumptions",
}
_EXECUTION_RESULT_KEYS = {
    "batch_artifact_path",
    "run_ids",
    "market_data_hash",
    "completed_candidates",
    "failed_candidates",
    "analysis_path",
}
_OBSERVED_RESPONSE_KEYS = {
    "topology",
    "structural_dimensions",
    "tested_ranges",
    "promising_regions",
    "rejected_regions",
}
_SIDE_INTERPRETATION_KEYS = {"aggregate", "long", "short", "asymmetry"}
_RISK_ASSESSMENT_KEYS = {
    "thinning_risk",
    "temporal_regime_concentration_concern",
    "other_confounders",
}
_BUDGET_KEYS = {
    "max_iterations",
    "max_wall_clock_seconds",
    "max_consecutive_agent_failures",
    "max_candidates_per_iteration",
}
_JOURNAL_V2_KEYS = {
    "contract_version",
    "session_id",
    "iteration_id",
    "timestamp",
    "baseline_git_sha",
    "research_phase",
    "hypothesis",
    "competing_explanation",
    "experiment_id",
    "candidate_ids",
    "window_policy",
    "strategy_context",
    "parameter_axes",
    "execution_accounting_assumptions",
    "batch_artifact_path",
    "run_ids",
    "market_data_hash",
    "outcome_classification",
    "side_interpretation",
    "risk_assessment",
    "conclusion",
    "next_question",
    "research_quality_assessment",
}
_PLAN_KEYS = {
    "contract_version",
    "session_id",
    "iteration_id",
    "phase",
    "hypothesis",
    "question",
    "market_property_proxy",
    "competing_explanation",
    "action",
    "canonical_request",
    "explanatory_metadata",
    "hard_stop_reason",
}
_RECEIPT_KEYS = {
    "contract_version",
    "session_id",
    "iteration_id",
    "baseline_git_sha",
    "canonical_request_sha256",
    "experiment_id",
    "candidate_ids",
    "executor_path",
    "executor_baseline_git_sha",
    "started_at",
    "ended_at",
    "exit_status",
    "adapter_output_sha256",
    "batch_artifact_path",
    "request_artifact_sha256",
    "summary_artifact_sha256",
    "manifest_artifact_sha256",
}
_CONTROL_KEYS = {
    "contract_version",
    "session_id",
    "iteration_id",
    "stage",
    "action",
    "plan_sha256",
    "request_sha256",
    "receipt_sha256",
    "interpretation_sha256",
    "execution_intent",
}
_NON_BATCH_ACTIONS = frozenset({"artifact_diagnostic", "terminal", "hard_stop"})
_FORBIDDEN_WORKER_NAMES = frozenset({"uv.lock", "sitecustomize.py", "market.sqlite3"})
_RESEARCH_ENV_PREFIX = "RESEARCH_"


class ContractError(ValueError):
    """A persisted AutoResearch document does not satisfy its v1 contract."""


def build_worker_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Preserve the CLI runtime while withholding the Research execution namespace."""

    inherited = os.environ if source is None else source
    return {
        key: value
        for key, value in inherited.items()
        if not key.upper().startswith(_RESEARCH_ENV_PREFIX)
    }


def build_executor_env(settings: Settings, source: dict[str, str] | None = None) -> dict[str, str]:
    """Build the canonical executor environment from one resolved Settings instance."""

    environment = build_worker_env(source)
    for field, value in settings.model_dump(mode="json").items():
        key = f"{_RESEARCH_ENV_PREFIX}{field.upper()}"
        environment[key] = value if isinstance(value, str) else json.dumps(value)
    return environment


_RESEARCH_SERVICE_BASE_URL_VAR = "BBB_AUTORESEARCH_RESEARCH_SERVICE_URL"


def resolve_research_service_base_url(source: dict[str, str] | None = None) -> str:
    """Resolve the one sanctioned Research Service API base URL for planning discovery.

    The launch profile wrapper (HOST/DOCKER), not the worker, owns this value -- a
    planning worker must never discover or guess Engine/MDS topology itself.
    """

    inherited = os.environ if source is None else source
    value = inherited.get(_RESEARCH_SERVICE_BASE_URL_VAR)
    if not value:
        raise ContractError(
            f"{_RESEARCH_SERVICE_BASE_URL_VAR} must be set by the launch profile wrapper"
        )
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractError(f"cannot hash {path}: {exc}") from exc


def validate_execution_plan(
    plan: dict[str, Any], state: dict[str, Any]
) -> BatchExperimentRequest | None:
    _require_exact_keys(plan, _PLAN_KEYS, "execution plan")
    if plan.get("contract_version") != PLAN_VERSION:
        raise ContractError(f"execution plan contract_version must be {PLAN_VERSION}")
    if plan.get("session_id") != state["session_id"]:
        raise ContractError("execution plan session_id differs from state")
    if plan.get("iteration_id") != state["iteration"] + 1:
        raise ContractError("execution plan iteration_id differs from state")
    if plan.get("phase") != state["phase"]:
        raise ContractError("execution plan phase differs from current state")
    for key in (
        "phase",
        "hypothesis",
        "question",
        "market_property_proxy",
        "competing_explanation",
    ):
        _require_string(plan, key)
    if not isinstance(plan["explanatory_metadata"], dict):
        raise ContractError("execution plan explanatory_metadata must be an object")
    action = plan.get("action")
    if action not in {"batch", *_NON_BATCH_ACTIONS}:
        raise ContractError("execution plan action is invalid")
    reason = plan.get("hard_stop_reason")
    if action == "hard_stop":
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError("hard_stop plan requires hard_stop_reason")
    elif reason is not None:
        raise ContractError("hard_stop_reason is only valid for hard_stop plan")
    if action != "batch":
        if plan.get("canonical_request") is not None:
            raise ContractError("non-batch plan must not contain canonical_request")
        return None
    if not isinstance(plan.get("canonical_request"), dict):
        raise ContractError("batch plan requires canonical_request")
    try:
        request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    except ValidationError as exc:
        raise ContractError(f"invalid canonical batch request: {exc}") from exc
    budget = state["budgets"].get("max_candidates_per_iteration")
    if budget is not None and len(request.candidates) > budget:
        raise ContractError("canonical request candidate count exceeds session budget")
    return request


def validate_execution_receipt(
    receipt: dict[str, Any],
    plan: dict[str, Any],
    state: dict[str, Any],
    request_path: Path,
    output_path: Path,
) -> None:
    _require_exact_keys(receipt, _RECEIPT_KEYS, "execution receipt")
    if receipt.get("contract_version") != RECEIPT_VERSION:
        raise ContractError(f"receipt contract_version must be {RECEIPT_VERSION}")
    if plan["action"] != "batch":
        raise ContractError("execution receipt is forbidden for non-batch action")
    request = validate_execution_plan(plan, state)
    assert request is not None
    expected = {
        "session_id": state["session_id"],
        "iteration_id": state["iteration"] + 1,
        "baseline_git_sha": state["baseline_git_sha"],
        "canonical_request_sha256": _sha256(request_path),
        "experiment_id": request.experiment_id,
        "candidate_ids": [item.candidate_id for item in request.candidates],
        "executor_path": "scripts/autoresearch_execute_batch.py",
        "executor_baseline_git_sha": state["baseline_git_sha"],
        "exit_status": 0,
        "adapter_output_sha256": _sha256(output_path),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ContractError(f"execution receipt {key} is inconsistent")
    for key in ("started_at", "ended_at"):
        _validate_datetime(receipt.get(key), f"execution receipt {key}")
    artifact = Path(receipt["batch_artifact_path"])
    for key, filename in (
        ("request_artifact_sha256", "request.json"),
        ("summary_artifact_sha256", "summary.json"),
        ("manifest_artifact_sha256", "manifest.json"),
    ):
        if receipt.get(key) != _sha256(artifact / filename):
            raise ContractError(f"execution receipt {key} is inconsistent")


def validate_iteration_control(control: dict[str, Any], state: dict[str, Any]) -> None:
    _require_exact_keys(control, _CONTROL_KEYS, "iteration control")
    if control.get("contract_version") != CONTROL_VERSION:
        raise ContractError("iteration control contract_version is invalid")
    if (
        control.get("session_id") != state["session_id"]
        or control.get("iteration_id") != state["iteration"] + 1
    ):
        raise ContractError("iteration control identity differs from state")
    stage = control.get("stage")
    if stage not in {
        "planning_pending",
        "request_prepared",
        "non_batch_plan_prepared",
        "execution_completed",
        "interpretation_prepared",
        "committed",
    }:
        raise ContractError("iteration control stage is invalid")
    for key in ("plan_sha256", "request_sha256", "receipt_sha256", "interpretation_sha256"):
        value = control[key]
        if value is not None and (
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        ):
            raise ContractError(f"iteration control {key} is invalid")
    action = control["action"]
    if stage == "planning_pending":
        if any(
            control[key] is not None
            for key in _CONTROL_KEYS - {"contract_version", "session_id", "iteration_id", "stage"}
        ):
            raise ContractError("planning_pending control contains prepared-stage values")
        return
    if action not in {"batch", *_NON_BATCH_ACTIONS} or control["plan_sha256"] is None:
        raise ContractError("prepared iteration control requires action and plan hash")
    if action in _NON_BATCH_ACTIONS:
        if (
            control["request_sha256"] is not None
            or control["receipt_sha256"] is not None
            or control["execution_intent"] is not None
        ):
            raise ContractError(
                "non-batch control must not contain execution intent/request/receipt"
            )
        if stage not in {"non_batch_plan_prepared", "interpretation_prepared", "committed"}:
            raise ContractError("non-batch control has an execution stage")
    else:
        if control["request_sha256"] is None or stage == "non_batch_plan_prepared":
            raise ContractError("batch control requires request hash and batch stage")
        if (
            stage in {"execution_completed", "interpretation_prepared", "committed"}
            and control["receipt_sha256"] is None
        ):
            raise ContractError("completed batch control requires receipt hash")
    if (
        stage in {"interpretation_prepared", "committed"}
        and control["interpretation_sha256"] is None
    ):
        raise ContractError("prepared interpretation control requires interpretation hash")


@dataclass(frozen=True)
class AgentRun:
    exit_code: int
    failure: str | None
    metadata: dict[str, Any]


class AgentRunner:
    """Provider-neutral fresh-process runner with a stage-scoped output boundary."""

    def __init__(
        self,
        command: str,
        repo_root: Path,
        session_root: Path,
        timeout: int | None,
        worker_env: dict[str, str],
    ):
        self.command = command
        self.repo_root = repo_root
        self.session_root = session_root
        self.timeout = timeout
        self.worker_env = dict(worker_env)

    def run(
        self,
        *,
        stage: str,
        prompt: str,
        prompt_path: Path,
        result_path: Path,
        analysis_dir: Path,
        stdout_path: Path,
        stderr_path: Path,
        values: dict[str, str],
        protected: dict[Path, str],
    ) -> AgentRun:
        prompt_path.write_text(prompt, encoding="utf-8")
        before = {path.relative_to(result_path.parent) for path in result_path.parent.rglob("*")}
        started_at = utc_now()
        started = time.monotonic()
        args = _command_args(
            self.command,
            {
                **values,
                "stage": stage,
                "result_file": str(result_path),
                "prompt_file": str(prompt_path),
            },
        )
        failure: str | None = None
        exit_code = 127
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                completed = subprocess.run(
                    args,
                    cwd=self.repo_root,
                    input=prompt.encode(),
                    stdout=stdout,
                    stderr=stderr,
                    timeout=self.timeout,
                    check=False,
                    env=self.worker_env,
                )
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
                failure = f"{stage} agent timeout"
            except OSError as exc:
                failure = f"{stage} agent spawn failed: {exc}"
        if failure is None and exit_code != 0:
            failure = f"{stage} agent exited with code {exit_code}"
        changed_protected = [
            str(path)
            for path, digest in protected.items()
            if not path.is_file() or _sha256(path) != digest
        ]
        after = {path.relative_to(result_path.parent) for path in result_path.parent.rglob("*")}
        created = after - before
        bad: list[str] = []
        for relative in created:
            path = result_path.parent / relative
            if path == result_path or path == analysis_dir or analysis_dir in path.parents:
                if (
                    path.is_symlink()
                    or path.name in _FORBIDDEN_WORKER_NAMES
                    or (
                        path.is_file()
                        and path != result_path
                        and path.suffix not in {".md", ".txt", ".json"}
                    )
                ):
                    bad.append(str(relative))
                continue
            if path not in {stdout_path, stderr_path, prompt_path}:
                bad.append(str(relative))
        if changed_protected or bad:
            failure = f"{stage} output boundary violation: protected={changed_protected}, unexpected={bad}"
        return AgentRun(
            exit_code,
            failure,
            {
                "stage": stage,
                "started_at": started_at,
                "ended_at": utc_now(),
                "duration_seconds": round(time.monotonic() - started, 6),
                "exit_code": exit_code,
                "failure": failure,
            },
        )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_session_id(value: str) -> str:
    if not SESSION_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise ContractError("session id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
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


def _require_exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractError(f"{context} fields differ: missing={missing}, extra={extra}")


def _require_nullable_string(value: dict[str, Any], key: str, context: str) -> None:
    item = value[key]
    if item is not None and (not isinstance(item, str) or not item.strip()):
        raise ContractError(f"{context}.{key} must be a non-empty string or null")


def _require_string_array(value: dict[str, Any], key: str, context: str) -> list[str]:
    item = value[key]
    if not isinstance(item, list) or any(not isinstance(entry, str) for entry in item):
        raise ContractError(f"{context}.{key} must be an array of strings")
    return item


def _require_object_array(value: dict[str, Any], key: str, context: str) -> list[dict[str, Any]]:
    item = value[key]
    if not isinstance(item, list) or any(not isinstance(entry, dict) for entry in item):
        raise ContractError(f"{context}.{key} must be an array of objects")
    return item


def _require_nullable_object(value: dict[str, Any], key: str, context: str) -> None:
    item = value[key]
    if item is not None and not isinstance(item, dict):
        raise ContractError(f"{context}.{key} must be an object or null")


def _validate_datetime(value: object, context: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ):
        raise ContractError(f"{context} must be an RFC 3339 date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{context} must be an RFC 3339 date-time string") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{context} must include a timezone")


def validate_state(state: dict[str, Any]) -> None:
    version = state.get("contract_version")
    if version not in {STATE_VERSION, STATE_VERSION_V2}:
        raise ContractError(f"contract_version must be {STATE_VERSION} or {STATE_VERSION_V2}")
    _require_exact_keys(
        state, _STATE_V2_KEYS if version == STATE_VERSION_V2 else _STATE_KEYS, "state"
    )
    if not isinstance(state.get("session_id"), str):
        raise ContractError("session_id must be a string")
    validate_session_id(state["session_id"])
    for key in (
        "research_program",
        "skill_path",
        "baseline_git_sha",
        "created_at",
        "updated_at",
        "phase",
    ):
        _require_string(state, key)
    if not re.fullmatch(r"[0-9a-f]{40}", state["baseline_git_sha"]):
        raise ContractError("baseline_git_sha must be a 40-character lowercase SHA")
    _validate_datetime(state["created_at"], "created_at")
    _validate_datetime(state["updated_at"], "updated_at")
    if not isinstance(state["strategy_context"], dict):
        raise ContractError("strategy_context must be an object")
    if state.get("status") not in {
        "initialized",
        "running",
        "hard_stopped",
        "completed",
        "cancelled",
    }:
        raise ContractError("invalid state status")
    if type(state.get("iteration")) is not int or state["iteration"] < 0:
        raise ContractError("iteration must be a non-negative integer")
    for key in (
        "competing_explanations",
        "structural_dimensions_known",
        "unresolved_questions",
        "completed_phases",
        "other_confounders",
    ):
        _require_string_array(state, key, "state")
    for key in (
        "tested_ranges",
        "observed_response_shapes",
        "promising_regions",
        "rejected_regions",
    ):
        _require_object_array(state, key, "state")
    findings = _require_object_array(state, "findings", "state")
    for index, finding in enumerate(findings):
        if "conclusion" not in finding or not isinstance(finding["conclusion"], str):
            raise ContractError(f"state.findings[{index}].conclusion must be a string")
        iteration = finding.get("iteration_id")
        if "iteration_id" in finding and (type(iteration) is not int or iteration < 0):
            raise ContractError(f"state.findings[{index}].iteration_id is invalid")
    for key in (
        "current_hypothesis",
        "aggregate_interpretation",
        "long_interpretation",
        "short_interpretation",
        "side_asymmetry",
        "thinning_risk",
        "temporal_regime_concentration_concern",
        "validation_status",
        "next_discriminating_question",
        "stop_reason",
    ):
        _require_nullable_string(state, key, "state")
    for key in ("next_experiment", "last_iteration_result"):
        _require_nullable_object(state, key, "state")
    budgets = state.get("budgets")
    if not isinstance(budgets, dict):
        raise ContractError("budgets must be an object")
    _require_exact_keys(budgets, _BUDGET_KEYS, "state.budgets")
    for key in (
        "max_iterations",
        "max_wall_clock_seconds",
        "max_candidates_per_iteration",
    ):
        item = budgets.get(key)
        if item is not None and (type(item) is not int or item < 1):
            raise ContractError(f"budgets.{key} must be a positive integer or null")
    failures = budgets.get("max_consecutive_agent_failures")
    if type(failures) is not int or failures < 1:
        raise ContractError("budgets.max_consecutive_agent_failures must be positive")
    stop_reason = state["stop_reason"]
    if state["status"] in {"hard_stopped", "cancelled"}:
        if not isinstance(stop_reason, str) or not stop_reason.strip():
            raise ContractError(f"{state['status']} state requires stop_reason")
    elif stop_reason is not None:
        raise ContractError("stop_reason must be null unless state is hard_stopped or cancelled")
    if version == STATE_VERSION_V2:
        try:
            policy = validate_policy(state["research_quality_policy"])
            binding = phase_binding(policy, state["phase"])
            if state["active_stage_binding"] != binding.model_dump(mode="json"):
                raise ContractError(
                    "active_stage_binding differs from current policy phase binding"
                )
            latest = state["latest_quality_assessment"]
            if latest is not None:
                assessment = validate_assessment(latest)
                if assessment.applied_policy_id != policy.policy_id:
                    raise ContractError("latest assessment uses a different policy")
            history = state["promotion_history"]
            if not isinstance(history, list):
                raise ContractError("promotion_history must be an array")
            history_keys = {"iteration_id", "region_id", "decision", "blockers"}
            for index, entry in enumerate(history):
                if not isinstance(entry, dict):
                    raise ContractError(f"promotion_history[{index}] must be an object")
                _require_exact_keys(entry, history_keys, f"promotion_history[{index}]")
                if type(entry["iteration_id"]) is not int or entry["iteration_id"] < 1:
                    raise ContractError(f"promotion_history[{index}].iteration_id is invalid")
                if entry["region_id"] is not None and (
                    not isinstance(entry["region_id"], str) or not entry["region_id"].strip()
                ):
                    raise ContractError(f"promotion_history[{index}].region_id is invalid")
                if entry["decision"] not in {
                    "continue_discovery",
                    "investigate_region",
                    "eligible_for_next_stage",
                    "validation_required",
                    "rejected_structurally",
                    "demoted_after_validation",
                    "no_stable_edge",
                }:
                    raise ContractError(f"promotion_history[{index}].decision is invalid")
                if not isinstance(entry["blockers"], list) or any(
                    not isinstance(blocker, dict) for blocker in entry["blockers"]
                ):
                    raise ContractError(f"promotion_history[{index}].blockers is invalid")
                for blocker in entry["blockers"]:
                    PromotionBlocker.model_validate(blocker)
        except ValidationError as exc:
            raise ContractError(f"invalid research quality state contract: {exc}") from exc
        except ValueError as exc:
            if isinstance(exc, ContractError):
                raise
            raise ContractError(f"invalid research quality state semantics: {exc}") from exc


def validate_state_transition(previous: dict[str, Any], current: dict[str, Any]) -> None:
    """Reject identity/iteration rewinds and all transitions out of terminal state."""

    validate_state(previous)
    validate_state(current)
    if previous["session_id"] != current["session_id"]:
        raise ContractError("session_id is immutable")
    if previous["baseline_git_sha"] != current["baseline_git_sha"]:
        raise ContractError("baseline_git_sha is immutable")
    if previous["contract_version"] != current["contract_version"]:
        raise ContractError(
            "state contract_version is immutable; migration must be operator-driven"
        )
    if previous.get("research_quality_policy") != current.get("research_quality_policy"):
        raise ContractError("research_quality_policy is immutable")
    if current["iteration"] < previous["iteration"]:
        raise ContractError("iteration cannot move backwards")
    if previous["status"] in TERMINAL_STATUSES and current != previous:
        raise ContractError("terminal session state cannot transition")


def validate_iteration_result(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    artifacts_root: Path | None = None,
) -> None:
    quality_aware = state.get("contract_version") == STATE_VERSION_V2
    expected_version = ITERATION_VERSION_V2 if quality_aware else ITERATION_VERSION
    if result.get("contract_version") != expected_version:
        raise ContractError(f"contract_version must be {expected_version}")
    _require_exact_keys(
        result, _ITERATION_V2_KEYS if quality_aware else _ITERATION_KEYS, "iteration result"
    )
    if result.get("session_id") != state["session_id"]:
        raise ContractError("iteration result session_id differs from state")
    expected = state["iteration"] + 1
    if type(result.get("iteration_id")) is not int or result["iteration_id"] != expected:
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
    for key in (
        "experiment",
        "execution_result",
        "observed_response",
        "side_interpretation",
        "risk_assessment",
    ):
        if not isinstance(result.get(key), dict):
            raise ContractError(f"{key} must be an object")
    experiment = result["experiment"]
    _require_exact_keys(experiment, _EXPERIMENT_KEYS, "experiment")
    if experiment.get("kind") not in {"batch", "artifact_diagnostic", "none"}:
        raise ContractError("experiment.kind is invalid")
    candidate_ids = _require_string_array(experiment, "candidate_ids", "experiment")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ContractError("experiment.candidate_ids must be unique")
    count = experiment["candidate_count"]
    if type(count) is not int or count < 0 or count != len(candidate_ids):
        raise ContractError("experiment.candidate_count must match candidate_ids")
    _require_object_array(experiment, "axes", "experiment")
    for key in ("window_policy", "strategy_context", "execution_accounting_assumptions"):
        _require_nullable_object(experiment, key, "experiment")
    experiment_id = experiment["experiment_id"]
    if experiment_id is not None and (
        not isinstance(experiment_id, str) or not experiment_id.strip()
    ):
        raise ContractError("experiment.experiment_id must be a non-empty string or null")
    execution = result["execution_result"]
    _require_exact_keys(execution, _EXECUTION_RESULT_KEYS, "execution_result")
    for key in ("completed_candidates", "failed_candidates"):
        if type(execution.get(key)) is not int or execution[key] < 0:
            raise ContractError(f"execution_result.{key} must be non-negative")
    run_ids = _require_string_array(execution, "run_ids", "execution_result")
    if len(run_ids) != len(set(run_ids)):
        raise ContractError("execution_result.run_ids must be unique")
    for key in ("batch_artifact_path", "market_data_hash", "analysis_path"):
        _require_nullable_string(execution, key, "execution_result")
    observed = result["observed_response"]
    _require_exact_keys(observed, _OBSERVED_RESPONSE_KEYS, "observed_response")
    _require_string(observed, "topology")
    _require_string_array(observed, "structural_dimensions", "observed_response")
    for key in ("tested_ranges", "promising_regions", "rejected_regions"):
        _require_object_array(observed, key, "observed_response")
    side = result["side_interpretation"]
    _require_exact_keys(side, _SIDE_INTERPRETATION_KEYS, "side_interpretation")
    for key in _SIDE_INTERPRETATION_KEYS:
        _require_string(side, key)
    risk = result["risk_assessment"]
    _require_exact_keys(risk, _RISK_ASSESSMENT_KEYS, "risk_assessment")
    _require_nullable_string(risk, "thinning_risk", "risk_assessment")
    _require_nullable_string(risk, "temporal_regime_concentration_concern", "risk_assessment")
    _require_string_array(risk, "other_confounders", "risk_assessment")
    hard_reason = result.get("hard_stop_reason")
    if status == "hard_stop" and (not isinstance(hard_reason, str) or not hard_reason.strip()):
        raise ContractError("hard_stop result requires hard_stop_reason")
    if status != "hard_stop" and hard_reason is not None:
        raise ContractError("hard_stop_reason is only valid for hard_stop")
    proposed = result.get("proposed_next_experiment")
    if proposed is not None:
        if not isinstance(proposed, dict):
            raise ContractError("proposed_next_experiment must be an object or null")
        for key in ("kind", "reason"):
            _require_string(proposed, key)
    canonical_summary: BatchExperimentResult | None = None
    if experiment["kind"] == "batch":
        if not isinstance(experiment.get("experiment_id"), str) or not experiment["experiment_id"]:
            raise ContractError("batch experiment requires experiment_id")
        if count < 1:
            raise ContractError("batch experiment requires at least one candidate")
        artifact_path = execution.get("batch_artifact_path")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise ContractError("batch execution requires batch_artifact_path")
        canonical_summary = _verify_batch_artifact(result, artifacts_root=artifacts_root)
    elif (
        experiment["kind"] == "artifact_diagnostic"
        and execution.get("batch_artifact_path") is not None
    ):
        if not isinstance(experiment.get("experiment_id"), str) or not experiment["experiment_id"]:
            raise ContractError("artifact diagnostic with batch evidence requires experiment_id")
        canonical_summary = _verify_batch_artifact(result, artifacts_root=artifacts_root)
    elif execution["completed_candidates"] + execution["failed_candidates"] != count:
        raise ContractError("execution candidate counts must match experiment candidate_count")
    candidate_budget = state["budgets"].get("max_candidates_per_iteration")
    if candidate_budget is not None and count > candidate_budget:
        raise ContractError("candidate count exceeds session budget")
    if quality_aware:
        try:
            policy = validate_policy(state["research_quality_policy"])
            assessment = validate_assessment(result["research_quality_assessment"])
            candidate_facts = (
                {
                    candidate.candidate_id: candidate.model_dump(mode="python")
                    for candidate in canonical_summary.candidates
                    if candidate.status == "completed"
                }
                if canonical_summary is not None
                else {}
            )
            enforce_quality_policy(
                policy,
                assessment,
                phase=result["phase"],
                candidate_facts=candidate_facts,
                prior_iteration=state["iteration"],
                analysis_path=execution["analysis_path"],
            )
        except (ValidationError, ValueError) as exc:
            raise ContractError(f"invalid research quality assessment: {exc}") from exc


def _verify_batch_artifact(
    result: dict[str, Any], *, artifacts_root: Path | None = None
) -> BatchExperimentResult:
    experiment = result["experiment"]
    execution = result["execution_result"]
    artifact = Path(execution["batch_artifact_path"])
    configured_root = artifacts_root if artifacts_root is not None else Settings().artifacts_root
    if ".." in artifact.parts:
        raise ContractError("batch artifact path must not contain traversal components")
    experiment_id = experiment["experiment_id"]
    try:
        raw_expected = configured_root.absolute() / "batches" / experiment_id
        if artifact.absolute() != raw_expected:
            raise ContractError("batch artifact path is not the canonical path for this experiment")
        resolved_root = configured_root.resolve(strict=True)
        resolved_artifact = artifact.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContractError(f"batch artifact path cannot be resolved safely: {exc}") from exc
    resolved_expected = resolved_root / "batches" / experiment_id
    if (
        not resolved_artifact.is_relative_to(resolved_root)
        or resolved_artifact != resolved_expected
    ):
        raise ContractError("batch artifact path escapes the canonical artifact namespace")
    required = ("request.json", "summary.json", "manifest.json")
    if not resolved_artifact.is_dir() or any(
        not (resolved_artifact / name).is_file() for name in required
    ):
        raise ContractError("batch artifact path is not a canonical persisted batch bundle")
    try:
        request = BatchExperimentRequest.model_validate_json(
            (resolved_artifact / "request.json").read_bytes()
        )
        summary_bytes = (resolved_artifact / "summary.json").read_bytes()
        summary = BatchExperimentResult.model_validate_json(summary_bytes)
        manifest = load_json(resolved_artifact / "manifest.json")
    except (OSError, ValidationError) as exc:
        raise ContractError(f"canonical batch artifact is invalid: {exc}") from exc
    manifest_keys = {
        "contract_version",
        "experiment_id",
        "summary_sha256",
        "candidate_count",
        "completed_count",
        "failed_count",
    }
    _require_exact_keys(manifest, manifest_keys, "batch manifest")
    if manifest["contract_version"] != "research_batch_artifacts.v1":
        raise ContractError("batch manifest contract_version is invalid")
    if not isinstance(manifest["experiment_id"], str):
        raise ContractError("batch manifest experiment_id is invalid")
    if not isinstance(manifest["summary_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest["summary_sha256"]
    ):
        raise ContractError("batch manifest summary_sha256 is invalid")
    for key in ("candidate_count", "completed_count", "failed_count"):
        if type(manifest[key]) is not int or manifest[key] < 0:
            raise ContractError(f"batch manifest {key} is invalid")
    identities = {
        experiment_id,
        request.experiment_id,
        summary.experiment_id,
        manifest["experiment_id"],
    }
    if len(identities) != 1:
        raise ContractError("batch experiment_id differs across iteration and artifacts")
    actual_summary_hash = hashlib.sha256(summary_bytes).hexdigest()
    if manifest["summary_sha256"] != actual_summary_hash:
        raise ContractError("batch summary sha256 differs from manifest")
    expected_counts = (
        experiment["candidate_count"],
        execution["completed_candidates"],
        execution["failed_candidates"],
    )
    summary_counts = (summary.candidate_count, summary.completed_count, summary.failed_count)
    manifest_counts = (
        manifest["candidate_count"],
        manifest["completed_count"],
        manifest["failed_count"],
    )
    if expected_counts != summary_counts or summary_counts != manifest_counts:
        raise ContractError("batch candidate counts differ across iteration and artifacts")
    request_ids = [candidate.candidate_id for candidate in request.candidates]
    summary_ids = [candidate.candidate_id for candidate in summary.candidates]
    if experiment["candidate_ids"] != request_ids or request_ids != summary_ids:
        raise ContractError("batch candidate IDs differ across iteration and artifacts")
    canonical_run_ids = [
        candidate.run_id for candidate in summary.candidates if candidate.status == "completed"
    ]
    if any(run_id is None for run_id in canonical_run_ids):
        raise ContractError("completed canonical batch candidate has no run_id")
    if execution["run_ids"] != canonical_run_ids:
        raise ContractError("iteration run_ids differ from canonical batch summary")
    canonical_hashes = {
        candidate.market_data_hash
        for candidate in summary.candidates
        if candidate.status == "completed"
    }
    if None in canonical_hashes:
        raise ContractError("completed canonical batch candidate has no market_data_hash")
    if len(canonical_hashes) > 1:
        raise ContractError("canonical batch candidates have different market_data_hash values")
    claimed_hash = execution["market_data_hash"]
    if canonical_hashes:
        if claimed_hash != next(iter(canonical_hashes)):
            raise ContractError("iteration market_data_hash differs from canonical batch summary")
    elif claimed_hash is not None:
        raise ContractError("iteration cannot claim market_data_hash with no completed candidates")
    return summary


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
    if event.get("contract_version") not in {JOURNAL_VERSION, JOURNAL_VERSION_V2}:
        raise ContractError(
            f"journal contract_version must be {JOURNAL_VERSION} or {JOURNAL_VERSION_V2}"
        )
    if event["contract_version"] == JOURNAL_VERSION_V2:
        _require_exact_keys(event, _JOURNAL_V2_KEYS, "journal event")
        if type(event["iteration_id"]) is not int or event["iteration_id"] < 1:
            raise ContractError("journal iteration_id must be positive")
        _validate_datetime(event["timestamp"], "journal timestamp")
        for key in (
            "session_id",
            "baseline_git_sha",
            "research_phase",
            "hypothesis",
            "outcome_classification",
            "conclusion",
            "next_question",
        ):
            _require_string(event, key)
        for key in ("candidate_ids", "run_ids", "competing_explanation"):
            _require_string_array(event, key, "journal event")
        try:
            validate_assessment(event["research_quality_assessment"])
        except ValidationError as exc:
            raise ContractError(f"invalid journal quality assessment: {exc}") from exc
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


def _render_stage_prompt(
    template_name: str,
    state: dict[str, Any],
    root: Path,
    iteration_root: Path,
    values: dict[str, Any],
) -> str:
    template = (root / "autoresearch" / "prompts" / template_name).read_text(encoding="utf-8")
    common = {
        "program_path": root / "autoresearch" / "program.md",
        "skill_path": root / state["skill_path"],
        "state_path": session_dir(state["session_id"], root) / "state.json",
        "journal_path": session_dir(state["session_id"], root) / "journal.jsonl",
        "iteration_dir": iteration_root,
        "iteration_id": state["iteration"] + 1,
        **values,
    }
    rendered = template.format(**{key: str(value) for key, value in common.items()})
    if state["iteration"] == 0:
        bootstrap = (root / "autoresearch" / "prompts" / "bootstrap.md").read_text(encoding="utf-8")
        return f"{bootstrap}\n\n{rendered}"
    return rendered


def render_planning_prompt(
    state: dict[str, Any],
    root: Path,
    iteration_root: Path,
    research_service_base_url: str,
) -> str:
    return _render_stage_prompt(
        "planning.md",
        state,
        root,
        iteration_root,
        {
            "plan_schema_path": root / "autoresearch/schemas/execution_plan.schema.json",
            "result_path": iteration_root / "execution_plan.json",
            "analysis_dir": iteration_root / "planning_analysis",
            "research_service_base_url": research_service_base_url,
        },
    )


def render_interpretation_prompt(
    state: dict[str, Any], root: Path, iteration_root: Path, action: str
) -> str:
    batch = action == "batch"
    values = {
        "result_path": iteration_root / "iteration_result.json",
        "plan_path": iteration_root / "execution_plan.json",
        "request_path": iteration_root / "canonical_request.json" if batch else "NONE",
        "execution_output_path": iteration_root / "execution_output.json" if batch else "NONE",
        "receipt_path": iteration_root / "execution_receipt.json" if batch else "NONE",
        "analysis_dir": iteration_root / "interpretation_analysis",
        "canonical_metric_paths": ", ".join(
            f"`{metric_path}`" for metric_path in sorted(CANONICAL_METRIC_PATHS)
        ),
        "stage_metric_role_contract": (
            describe_stage_metric_role_contract(state["active_stage_binding"]["stage_kind"])
            if state["contract_version"] == STATE_VERSION_V2
            else "N/A (legacy v1 contract has no stage metric-role assessment)."
        ),
        "result_schema_path": root
        / "autoresearch"
        / "schemas"
        / (
            "iteration_result.v2.schema.json"
            if state["contract_version"] == STATE_VERSION_V2
            else "iteration_result.schema.json"
        ),
    }
    return _render_stage_prompt("interpretation.md", state, root, iteration_root, values)


def render_prompt(
    state: dict[str, Any], root: Path, iteration_root: Path, research_service_base_url: str
) -> str:
    """Compatibility alias for callers that inspect the first-stage prompt."""
    return render_planning_prompt(state, root, iteration_root, research_service_base_url)


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
        return {
            "contract_version": "bbb_autoresearch_supervisor_metadata.v2",
            "planning_attempts": [],
            "interpretation_attempts": [],
        }
    metadata = load_json(path)
    if "attempts" in metadata:
        if not isinstance(metadata["attempts"], list):
            raise ContractError("supervisor metadata attempts must be an array")
    else:
        for key in ("planning_attempts", "interpretation_attempts"):
            if not isinstance(metadata.get(key), list):
                raise ContractError(f"supervisor metadata {key} must be an array")
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
    event = {
        "contract_version": (
            JOURNAL_VERSION_V2 if state["contract_version"] == STATE_VERSION_V2 else JOURNAL_VERSION
        ),
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
        "execution_accounting_assumptions": experiment.get("execution_accounting_assumptions"),
        "batch_artifact_path": execution.get("batch_artifact_path"),
        "run_ids": execution.get("run_ids", []),
        "market_data_hash": execution.get("market_data_hash"),
        "outcome_classification": result["observed_response"].get("topology"),
        "side_interpretation": result["side_interpretation"],
        "risk_assessment": result["risk_assessment"],
        "conclusion": result["conclusion"],
        "next_question": result["next_discriminating_question"],
    }
    if state["contract_version"] == STATE_VERSION_V2:
        event["research_quality_assessment"] = result["research_quality_assessment"]
    return event


def _advance_state(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    observed = result["observed_response"]
    side = result["side_interpretation"]
    risk = result["risk_assessment"]
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
        findings=[
            *state["findings"],
            {"iteration_id": result["iteration_id"], "conclusion": result["conclusion"]},
        ],
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
            *state["unresolved_questions"],
            result["next_discriminating_question"],
        ],
        aggregate_interpretation=side["aggregate"],
        long_interpretation=side["long"],
        short_interpretation=side["short"],
        side_asymmetry=side["asymmetry"],
        thinning_risk=risk["thinning_risk"],
        temporal_regime_concentration_concern=risk["temporal_regime_concentration_concern"],
        other_confounders=risk["other_confounders"],
        next_discriminating_question=result["next_discriminating_question"],
        next_experiment=proposed,
        last_iteration_result={
            "iteration_id": result["iteration_id"],
            "status": result["status"],
            "conclusion": result["conclusion"],
        },
        stop_reason=(
            result.get("hard_stop_reason") or "worker reported failed iteration"
            if next_status == "hard_stopped"
            else None
        ),
    )
    if state["contract_version"] == STATE_VERSION_V2:
        policy = validate_policy(state["research_quality_policy"])
        assessment = result["research_quality_assessment"]
        promotion = assessment["promotion"]
        subject = assessment["promotion_subject"]
        updated.update(
            active_stage_binding=phase_binding(policy, result["phase"]).model_dump(mode="json"),
            latest_quality_assessment=assessment,
            promotion_history=[
                *state["promotion_history"],
                {
                    "iteration_id": result["iteration_id"],
                    "region_id": subject["region_id"] if subject is not None else None,
                    "decision": promotion["decision"],
                    "blockers": promotion["blockers"],
                },
            ],
        )
    validate_state(updated)
    validate_state_transition(state, updated)
    return updated


def _initial_control(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": CONTROL_VERSION,
        "session_id": state["session_id"],
        "iteration_id": state["iteration"] + 1,
        "stage": "planning_pending",
        "action": None,
        "plan_sha256": None,
        "request_sha256": None,
        "receipt_sha256": None,
        "interpretation_sha256": None,
        "execution_intent": None,
    }


def _freeze_plan(
    plan_path: Path, control_path: Path, plan: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    request = validate_execution_plan(plan, state)
    atomic_write_json(plan_path, plan)
    control = _initial_control(state)
    control.update(
        action=plan["action"],
        plan_sha256=_sha256(plan_path),
        stage="request_prepared" if request is not None else "non_batch_plan_prepared",
    )
    if request is not None:
        request_path = plan_path.parent / "canonical_request.json"
        atomic_write_json(request_path, request.model_dump(mode="json"))
        control["request_sha256"] = _sha256(request_path)
    validate_iteration_control(control, state)
    atomic_write_json(control_path, control)
    return control


def _complete_execution_receipt(
    iteration_root: Path, state: dict[str, Any], plan: dict[str, Any], control: dict[str, Any]
) -> dict[str, Any]:
    request_path = iteration_root / "canonical_request.json"
    output_path = iteration_root / "execution_output.json"
    output = load_json(output_path)
    if output.get("contract_version") != "bbb_autoresearch_batch_execution.v1":
        raise ContractError("canonical adapter output contract_version is invalid")
    try:
        result = BatchExperimentResult.model_validate(output["result"])
        artifact_path = Path(output["persisted_batch"]["artifact_path"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise ContractError(f"canonical adapter output is invalid: {exc}") from exc
    request = validate_execution_plan(plan, state)
    assert request is not None
    if result.experiment_id != request.experiment_id:
        raise ContractError("canonical adapter output experiment_id differs from request")
    receipt = {
        "contract_version": RECEIPT_VERSION,
        "session_id": state["session_id"],
        "iteration_id": state["iteration"] + 1,
        "baseline_git_sha": state["baseline_git_sha"],
        "canonical_request_sha256": _sha256(request_path),
        "experiment_id": request.experiment_id,
        "candidate_ids": [item.candidate_id for item in request.candidates],
        "executor_path": "scripts/autoresearch_execute_batch.py",
        "executor_baseline_git_sha": state["baseline_git_sha"],
        "started_at": control["execution_intent"]["started_at"],
        "ended_at": utc_now(),
        "exit_status": 0,
        "adapter_output_sha256": _sha256(output_path),
        "batch_artifact_path": str(artifact_path),
        "request_artifact_sha256": _sha256(artifact_path / "request.json"),
        "summary_artifact_sha256": _sha256(artifact_path / "summary.json"),
        "manifest_artifact_sha256": _sha256(artifact_path / "manifest.json"),
    }
    receipt_path = iteration_root / "execution_receipt.json"
    atomic_write_json(receipt_path, receipt)
    validate_execution_receipt(receipt, plan, state, request_path, output_path)
    control.update(stage="execution_completed", receipt_sha256=_sha256(receipt_path))
    atomic_write_json(iteration_root / "iteration_control.json", control)
    return control


def _execute_canonical_batch(
    repo_root: Path,
    iteration_root: Path,
    state: dict[str, Any],
    plan: dict[str, Any],
    control: dict[str, Any],
    timeout: int | None,
    executor_env: dict[str, str],
) -> dict[str, Any]:
    request_path = iteration_root / "canonical_request.json"
    output_path = iteration_root / "execution_output.json"
    intent = {"started_at": utc_now(), "request_sha256": _sha256(request_path)}
    control = dict(control)
    control["execution_intent"] = intent
    atomic_write_json(iteration_root / "iteration_control.json", control)
    with (
        (iteration_root / "executor.stdout.log").open("wb") as stdout,
        (iteration_root / "executor.stderr.log").open("wb") as stderr,
    ):
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/autoresearch_execute_batch.py"),
                    "--input",
                    str(request_path),
                    "--output",
                    str(output_path),
                ],
                cwd=repo_root,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
                env=executor_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContractError(
                "canonical executor timeout; no worker fallback is permitted"
            ) from exc
        except OSError as exc:
            raise ContractError(f"canonical executor spawn failed: {exc}") from exc
    if completed.returncode != 0 or not output_path.is_file():
        raise ContractError(f"canonical executor failed with exit status {completed.returncode}")
    return _complete_execution_receipt(iteration_root, state, plan, control)


def _validate_interpretation_binding(
    result: dict[str, Any], plan: dict[str, Any], state: dict[str, Any], iteration_root: Path
) -> None:
    if (
        result["phase"] != plan["phase"]
        or result["hypothesis"] != plan["hypothesis"]
        or result["market_property_proxy"] != plan["market_property_proxy"]
    ):
        raise ContractError(
            "interpretation differs from frozen plan identity or scientific question"
        )
    action = plan["action"]
    if action == "batch":
        request_path = iteration_root / "canonical_request.json"
        output_path = iteration_root / "execution_output.json"
        receipt_path = iteration_root / "execution_receipt.json"
        receipt = load_json(receipt_path)
        validate_execution_receipt(receipt, plan, state, request_path, output_path)
        request = BatchExperimentRequest.model_validate_json(request_path.read_bytes())
        experiment = result["experiment"]
        if (
            experiment["kind"] != "batch"
            or experiment["experiment_id"] != request.experiment_id
            or experiment["candidate_ids"] != [c.candidate_id for c in request.candidates]
        ):
            raise ContractError("interpretation experiment differs from frozen request")
        if result["execution_result"]["batch_artifact_path"] != receipt["batch_artifact_path"]:
            raise ContractError("interpretation artifact path differs from execution receipt")
    else:
        if (
            (iteration_root / "execution_receipt.json").exists()
            or (iteration_root / "execution_output.json").exists()
            or plan.get("canonical_request") is not None
        ):
            raise ContractError("non-batch action must have no execution result or receipt")
        expected_kind = "artifact_diagnostic" if action == "artifact_diagnostic" else "none"
        if result["experiment"]["kind"] != expected_kind:
            raise ContractError("non-batch interpretation kind differs from frozen plan")
        if action == "hard_stop" and result["status"] != "hard_stop":
            raise ContractError("hard_stop plan requires hard_stop interpretation")
        if action == "terminal" and result.get("proposed_next_experiment") is not None:
            raise ContractError("terminal interpretation must not propose another experiment")
        if action == "artifact_diagnostic":
            planned_artifact = plan["explanatory_metadata"].get("batch_artifact_path")
            if result["execution_result"]["batch_artifact_path"] != planned_artifact:
                raise ContractError("artifact diagnostic evidence differs from frozen plan")


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
    bootstrap = load_json(root / "bootstrap.json")
    if bootstrap.get("execution_protocol") != "bbb_autoresearch_supervisor_execution.v1":
        state = load_json(state_path)
        _write_hard_stop(
            state_path,
            state,
            "session predates supervisor-brokered execution; initialize a new session",
        )
        return 2
    research_settings = Settings()
    worker_env = build_worker_env()
    executor_env = build_executor_env(research_settings)
    research_service_base_url = resolve_research_service_base_url()
    while True:
        state = load_json(state_path)
        validate_state(state)
        if state["status"] in TERMINAL_STATUSES:
            return 0
        if (root / "cancel.requested.json").exists():
            cancelled = dict(state)
            cancelled.update(
                status="cancelled", stop_reason="operator cancellation", updated_at=utc_now()
            )
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
        control_path = iteration_root / "iteration_control.json"
        control = load_json(control_path) if control_path.exists() else _initial_control(state)
        validate_iteration_control(control, state)
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
            plan = load_json(iteration_root / "execution_plan.json")
            validate_execution_plan(plan, state)
            validate_iteration_result(recovered, state)
            _validate_interpretation_binding(recovered, plan, state, iteration_root)
            atomic_write_json(state_path, _advance_state(state, recovered))
            continue
        metadata_path = iteration_root / "supervisor_metadata.json"
        metadata = _read_metadata(metadata_path)
        metadata.setdefault("planning_attempts", metadata.pop("attempts", []))
        metadata.setdefault("interpretation_attempts", [])
        failure_limit = (
            max_agent_failures
            if max_agent_failures is not None
            else state["budgets"]["max_consecutive_agent_failures"]
        )
        runner = AgentRunner(agent_command, repo_root, root, agent_timeout_seconds, worker_env)
        values = {
            "session_dir": str(root),
            "iteration_dir": str(iteration_root),
            "iteration_id": str(iteration_id),
        }
        durable_protected = {
            path: _sha256(path) for path in (state_path, journal_path, root / "bootstrap.json")
        }

        if control["stage"] == "planning_pending":
            plan_path = iteration_root / "execution_plan.json"
            prompt = render_planning_prompt(
                state, repo_root, iteration_root, research_service_base_url
            )
            attempts = metadata["planning_attempts"]
            while len(attempts) < failure_limit:
                retry = len(attempts)
                plan_path.unlink(missing_ok=True)
                run = runner.run(
                    stage="planning",
                    prompt=prompt,
                    prompt_path=iteration_root / "planning_prompt.txt",
                    result_path=plan_path,
                    analysis_dir=iteration_root / "planning_analysis",
                    stdout_path=iteration_root
                    / (
                        "planning.stdout.log"
                        if retry == 0
                        else f"planning.stdout.retry-{retry:02d}.log"
                    ),
                    stderr_path=iteration_root
                    / (
                        "planning.stderr.log"
                        if retry == 0
                        else f"planning.stderr.retry-{retry:02d}.log"
                    ),
                    values=values,
                    protected=durable_protected,
                )
                failure = run.failure
                if failure is None:
                    try:
                        plan = load_json(plan_path)
                        validate_execution_plan(plan, state)
                        control = _freeze_plan(plan_path, control_path, plan, state)
                    except ContractError as exc:
                        failure = f"invalid execution plan: {exc}"
                attempts.append({**run.metadata, "retry_index": retry, "failure": failure})
                atomic_write_json(metadata_path, metadata)
                if failure is not None and "output boundary violation" in failure:
                    _write_hard_stop(state_path, state, failure)
                    return 2
                violations = repository_violations(repo_root, root)
                if violations:
                    _write_hard_stop(
                        state_path, state, f"unauthorized repository changes: {violations}"
                    )
                    return 2
                if failure is None:
                    break
            if control["stage"] == "planning_pending":
                _write_hard_stop(
                    state_path, state, f"repeated planning failure: {len(attempts)} attempts"
                )
                return 2

        plan_path = iteration_root / "execution_plan.json"
        plan = load_json(plan_path)
        validate_execution_plan(plan, state)
        if _sha256(plan_path) != control["plan_sha256"]:
            _write_hard_stop(state_path, state, "frozen execution plan changed")
            return 2

        if control["stage"] == "request_prepared":
            if control["execution_intent"] is not None:
                # A valid completed receipt is recoverable; an otherwise ambiguous launch is not.
                if (iteration_root / "execution_receipt.json").is_file() and (
                    iteration_root / "execution_output.json"
                ).is_file():
                    receipt = load_json(iteration_root / "execution_receipt.json")
                    validate_execution_receipt(
                        receipt,
                        plan,
                        state,
                        iteration_root / "canonical_request.json",
                        iteration_root / "execution_output.json",
                    )
                    control.update(
                        stage="execution_completed",
                        receipt_sha256=_sha256(iteration_root / "execution_receipt.json"),
                    )
                    atomic_write_json(control_path, control)
                elif (iteration_root / "execution_output.json").is_file():
                    try:
                        control = _complete_execution_receipt(iteration_root, state, plan, control)
                    except ContractError as exc:
                        _write_hard_stop(
                            state_path, state, f"ambiguous canonical executor outcome: {exc}"
                        )
                        return 2
                else:
                    _write_hard_stop(state_path, state, "ambiguous canonical executor outcome")
                    return 2
            else:
                try:
                    control = _execute_canonical_batch(
                        repo_root,
                        iteration_root,
                        state,
                        plan,
                        control,
                        agent_timeout_seconds,
                        executor_env,
                    )
                except ContractError as exc:
                    _write_hard_stop(state_path, state, str(exc))
                    return 2

        if control["stage"] in {"execution_completed", "non_batch_plan_prepared"}:
            prompt = render_interpretation_prompt(state, repo_root, iteration_root, plan["action"])
            attempts = metadata["interpretation_attempts"]
            protected_paths = [plan_path, control_path]
            if plan["action"] == "batch":
                protected_paths += [
                    iteration_root / "canonical_request.json",
                    iteration_root / "execution_output.json",
                    iteration_root / "execution_receipt.json",
                ]
            protected = {
                **durable_protected,
                **{path: _sha256(path) for path in protected_paths},
            }
            while len(attempts) < failure_limit:
                retry = len(attempts)
                result_path.unlink(missing_ok=True)
                run = runner.run(
                    stage="interpretation",
                    prompt=prompt,
                    prompt_path=iteration_root / "interpretation_prompt.txt",
                    result_path=result_path,
                    analysis_dir=iteration_root / "interpretation_analysis",
                    stdout_path=iteration_root
                    / (
                        "interpretation.stdout.log"
                        if retry == 0
                        else f"interpretation.stdout.retry-{retry:02d}.log"
                    ),
                    stderr_path=iteration_root
                    / (
                        "interpretation.stderr.log"
                        if retry == 0
                        else f"interpretation.stderr.retry-{retry:02d}.log"
                    ),
                    values=values,
                    protected=protected,
                )
                failure = run.failure
                if failure is None:
                    try:
                        result = load_json(result_path)
                        validate_iteration_result(result, state)
                        _validate_interpretation_binding(result, plan, state, iteration_root)
                        control.update(
                            stage="interpretation_prepared",
                            interpretation_sha256=_sha256(result_path),
                        )
                        atomic_write_json(control_path, control)
                    except (ContractError, ValidationError) as exc:
                        failure = f"invalid interpretation result: {exc}"
                attempts.append({**run.metadata, "retry_index": retry, "failure": failure})
                atomic_write_json(metadata_path, metadata)
                if failure is not None and "output boundary violation" in failure:
                    _write_hard_stop(state_path, state, failure)
                    return 2
                violations = repository_violations(repo_root, root)
                if violations:
                    _write_hard_stop(
                        state_path, state, f"unauthorized repository changes: {violations}"
                    )
                    return 2
                if failure is None:
                    break
            if control["stage"] != "interpretation_prepared":
                _write_hard_stop(
                    state_path, state, f"repeated interpretation failure: {len(attempts)} attempts"
                )
                return 2

        if control["stage"] == "interpretation_prepared":
            if _sha256(result_path) != control["interpretation_sha256"]:
                _write_hard_stop(state_path, state, "prepared interpretation changed")
                return 2
            result = load_json(result_path)
            validate_iteration_result(result, state)
            _validate_interpretation_binding(result, plan, state, iteration_root)
            append_journal(journal_path, _journal_event(state, result))
            updated = _advance_state(state, result)
            control["stage"] = "committed"
            atomic_write_json(control_path, control)
            atomic_write_json(state_path, updated)
            if updated["status"] in TERMINAL_STATUSES:
                return 0 if updated["status"] in {"completed", "cancelled"} else 2


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
