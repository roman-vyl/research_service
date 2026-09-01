from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from autoresearch_init import initialize_session  # noqa: E402
from autoresearch_supervisor import (  # noqa: E402
    JOURNAL_VERSION,
    ContractError,
    append_journal,
    atomic_write_json,
    load_json,
    validate_session_id,
    validate_state,
    validate_state_transition,
    validate_iteration_result,
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".claude/skills/ema-anchor-edge-research").mkdir(parents=True)
    (tmp_path / ".claude/skills/ema-anchor-edge-research/SKILL.md").write_text("policy")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    return tmp_path


def _template(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "research_program": "ema-anchor-edge-research",
                "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
                "strategy_context": {"strategy_id": "ema_pullback"},
                "budgets": {"max_consecutive_agent_failures": 3},
            }
        )
    )
    return path


def test_initialization_validates_and_atomically_persists_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    root = initialize_session("session-1", _template(repo / "template.json"), repo)

    state = load_json(root / "state.json")
    validate_state(state)
    assert state["iteration"] == 0
    assert state["baseline_git_sha"] == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert (root / "journal.jsonl").read_text() == ""
    assert not list(root.glob(".state.json.*"))


def test_invalid_state_and_session_ids_fail_closed(tmp_path: Path) -> None:
    for value in ("", "../escape", "bad/name", "."):
        with pytest.raises(ContractError):
            validate_session_id(value)
    with pytest.raises(ContractError, match="contract_version"):
        validate_state({"contract_version": "wrong"})


def test_invalid_state_transitions_are_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    root = initialize_session("session-1", _template(repo / "template.json"), repo)
    state = load_json(root / "state.json")
    rewound = dict(state, iteration=-1)
    with pytest.raises(ContractError):
        validate_state_transition(state, rewound)
    terminal = dict(state, status="completed")
    validate_state(terminal)
    with pytest.raises(ContractError, match="terminal"):
        validate_state_transition(terminal, dict(terminal, status="running"))


def test_atomic_write_replaces_complete_document(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_json(target, {"value": 1})
    atomic_write_json(target, {"value": 2})
    assert json.loads(target.read_text()) == {"value": 2}
    assert not list(tmp_path.glob(".state.json.*"))


def test_journal_append_never_rewrites_prior_rows(tmp_path: Path) -> None:
    target = tmp_path / "journal.jsonl"
    first = {"contract_version": JOURNAL_VERSION, "iteration_id": 1}
    second = {"contract_version": JOURNAL_VERSION, "iteration_id": 2}
    append_journal(target, first)
    original = target.read_bytes()
    append_journal(target, second)
    assert target.read_bytes().startswith(original)
    assert [json.loads(row)["iteration_id"] for row in target.read_text().splitlines()] == [1, 2]


def test_existing_session_is_not_overwritten(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    template = _template(repo / "template.json")
    initialize_session("session-1", template, repo)
    with pytest.raises(FileExistsError):
        initialize_session("session-1", template, repo)


def _valid_iteration() -> dict[str, object]:
    return {
        "contract_version": "bbb_autoresearch_iteration.v1",
        "session_id": "session-1",
        "iteration_id": 1,
        "status": "completed",
        "phase": "baseline",
        "hypothesis": "hypothesis",
        "market_property_proxy": "proxy",
        "experiment": {
            "kind": "artifact_diagnostic",
            "experiment_id": None,
            "axes": [],
            "candidate_ids": [],
            "candidate_count": 0,
            "window_policy": None,
            "strategy_context": None,
            "execution_accounting_assumptions": None,
        },
        "execution_result": {
            "batch_artifact_path": None,
            "run_ids": [],
            "market_data_hash": None,
            "completed_candidates": 0,
            "failed_candidates": 0,
            "analysis_path": None,
        },
        "observed_response": {
            "topology": "insufficient_evidence",
            "structural_dimensions": [],
            "tested_ranges": [],
            "promising_regions": [],
            "rejected_regions": [],
        },
        "side_interpretation": {
            "aggregate": "aggregate",
            "long": "long",
            "short": "short",
            "asymmetry": "asymmetry",
        },
        "risk_assessment": {
            "thinning_risk": None,
            "temporal_regime_concentration_concern": None,
            "other_confounders": [],
        },
        "conclusion": "conclusion",
        "next_discriminating_question": "question",
        "proposed_next_experiment": None,
        "hard_stop_reason": None,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(unexpected=True),
        lambda value: value["experiment"].update(unexpected=True),
        lambda value: value["experiment"].update(candidate_count=1),
        lambda value: value["experiment"].update(candidate_ids=["same", "same"], candidate_count=2),
        lambda value: value["observed_response"].update(unexpected=True),
        lambda value: value["observed_response"].update(topology=1),
        lambda value: value["side_interpretation"].pop("asymmetry"),
        lambda value: value["risk_assessment"].update(other_confounders="not-an-array"),
        lambda value: value.update(status="hard_stop", hard_stop_reason=None),
        lambda value: value.update(status="completed", hard_stop_reason="not allowed"),
    ],
)
def test_schema_invalid_iteration_documents_are_rejected(
    tmp_path: Path, mutate
) -> None:
    repo = _repo(tmp_path)
    root = initialize_session("session-1", _template(repo / "template.json"), repo)
    state = load_json(root / "state.json")
    result = _valid_iteration()
    mutate(result)
    with pytest.raises(ContractError):
        validate_iteration_result(result, state)


def test_state_rejects_schema_extra_and_nested_type_mismatch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    root = initialize_session("session-1", _template(repo / "template.json"), repo)
    state = load_json(root / "state.json")
    with pytest.raises(ContractError, match="extra"):
        validate_state({**state, "unexpected": True})
    bad_budgets = dict(state["budgets"], unexpected=True)
    with pytest.raises(ContractError, match="budgets"):
        validate_state({**state, "budgets": bad_budgets})
    with pytest.raises(ContractError, match="iteration_id"):
        validate_state({**state, "findings": [{"conclusion": "x", "iteration_id": None}]})
