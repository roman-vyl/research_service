from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from autoresearch_init import initialize_session  # noqa: E402
from autoresearch_supervisor import (  # noqa: E402
    _advance_state,
    _journal_event,
    append_journal,
    atomic_write_json,
    load_json,
    run_supervisor,
)


FAKE_AGENT = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

result_path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
iteration_id = int(result_path.parent.name)
if mode == "crash":
    raise SystemExit(7)
if mode == "malformed":
    result_path.write_text("{bad json")
    raise SystemExit(0)
if mode == "mutate":
    pathlib.Path("tracked.txt").write_text("changed\n")

proposed = None
status = "completed"
hard_reason = None
if mode == "continue_then_complete" and iteration_id == 1:
    proposed = {"kind": "artifact_diagnostic", "reason": "next information"}
if mode == "hard_stop":
    status = "hard_stop"
    hard_reason = "contract ambiguity"
result = {
  "contract_version": "bbb_autoresearch_iteration.v1",
  "session_id": "s1", "iteration_id": iteration_id, "status": status,
  "phase": "baseline", "hypothesis": "test hypothesis",
  "market_property_proxy": "test proxy",
  "experiment": {"kind": "artifact_diagnostic", "experiment_id": None, "axes": [],
    "candidate_ids": [], "candidate_count": 0, "window_policy": None,
    "strategy_context": {"strategy_id": "ema_pullback"},
    "execution_accounting_assumptions": None},
  "execution_result": {"batch_artifact_path": None, "run_ids": [],
    "market_data_hash": None, "completed_candidates": 0, "failed_candidates": 0,
    "analysis_path": None},
  "observed_response": {"topology": "insufficient_evidence", "structural_dimensions": [],
    "tested_ranges": [], "promising_regions": [], "rejected_regions": [],
    "temporal_regime_concentration_concern": None},
  "side_interpretation": {"aggregate": "none", "long": "none", "short": "none"},
  "confounders": ["none"], "conclusion": "one iteration complete",
  "next_discriminating_question": "what next?",
  "proposed_next_experiment": proposed, "hard_stop_reason": hard_reason
}
result_path.write_text(json.dumps(result))
'''


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "autoresearch/prompts").mkdir(parents=True)
    source_root = Path(__file__).parents[1]
    prompt = (source_root / "autoresearch/prompts/iteration.md").read_text()
    (tmp_path / "autoresearch/prompts/iteration.md").write_text(prompt)
    bootstrap = (source_root / "autoresearch/prompts/bootstrap.md").read_text()
    (tmp_path / "autoresearch/prompts/bootstrap.md").write_text(bootstrap)
    (tmp_path / "autoresearch/program.md").write_text("program")
    (tmp_path / ".claude/skills/ema-anchor-edge-research").mkdir(parents=True)
    (tmp_path / ".claude/skills/ema-anchor-edge-research/SKILL.md").write_text("skill")
    (tmp_path / ".gitignore").write_text("var/\n")
    (tmp_path / "tracked.txt").write_text("fixed\n")
    (tmp_path / "fake_agent.py").write_text(FAKE_AGENT)
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps(
            {
                "research_program": "ema-anchor-edge-research",
                "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
                "strategy_context": {"strategy_id": "ema_pullback"},
                "budgets": {"max_consecutive_agent_failures": 2},
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    root = initialize_session("s1", template, tmp_path)
    return tmp_path, root


def _command(repo: Path, mode: str) -> str:
    return f"{sys.executable} {repo / 'fake_agent.py'} {{result_file}} {mode}"


def test_fresh_invocation_continues_then_completes(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    code = run_supervisor(
        session_id="s1", agent_command=_command(repo, "continue_then_complete"), repo_root=repo
    )
    state = load_json(root / "state.json")
    assert code == 0
    assert state["status"] == "completed"
    assert state["iteration"] == 2
    assert (root / "iterations/0001/stdout.log").is_file()
    assert (root / "iterations/0002/stdout.log").is_file()
    assert len((root / "journal.jsonl").read_text().splitlines()) == 2


def test_restart_resumes_at_next_iteration(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    seed_path = root / "seed/0001/iteration_result.json"
    seed_path.parent.mkdir(parents=True)
    subprocess.run(
        [sys.executable, str(repo / "fake_agent.py"), str(seed_path), "continue_then_complete"],
        cwd=repo,
        check=True,
    )
    first_result = json.loads(seed_path.read_text())
    append_journal(root / "journal.jsonl", _journal_event(state, first_result))
    atomic_write_json(root / "state.json", _advance_state(state, first_result))

    assert run_supervisor(
        session_id="s1", agent_command=_command(repo, "continue_then_complete"), repo_root=repo
    ) == 0
    assert load_json(root / "state.json")["iteration"] == 2
    assert not (root / "iterations/0001").exists()
    assert (root / "iterations/0002").exists()


def test_hard_stop_result_launches_no_next_worker(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    assert run_supervisor(
        session_id="s1", agent_command=_command(repo, "hard_stop"), repo_root=repo
    ) == 2
    assert load_json(root / "state.json")["status"] == "hard_stopped"
    assert not (root / "iterations/0002").exists()


def test_forbidden_mutation_hard_stops_and_preserves_evidence(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    assert run_supervisor(
        session_id="s1", agent_command=_command(repo, "mutate"), repo_root=repo
    ) == 2
    assert (repo / "tracked.txt").read_text() == "changed\n"
    assert "tracked.txt" in load_json(root / "state.json")["stop_reason"]


def test_malformed_result_and_crash_retry_are_bounded(tmp_path: Path) -> None:
    for name, mode in (("malformed", "malformed"), ("crash", "crash")):
        repo, root = _repo(tmp_path / name)
        assert run_supervisor(
            session_id="s1",
            agent_command=_command(repo, mode),
            repo_root=repo,
            max_agent_failures=2,
        ) == 2
        metadata = load_json(root / "iterations/0001/supervisor_metadata.json")
        assert len(metadata["attempts"]) == 2
        assert load_json(root / "state.json")["status"] == "hard_stopped"


def test_cancellation_and_budget_launch_no_worker(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path / "cancel")
    (root / "cancel.requested.json").write_text("{}")
    assert run_supervisor(session_id="s1", agent_command="missing", repo_root=repo) == 0
    assert load_json(root / "state.json")["status"] == "cancelled"
    assert not any((root / "iterations").iterdir())

    repo, root = _repo(tmp_path / "budget")
    state = load_json(root / "state.json")
    state["budgets"]["max_iterations"] = 1
    state["iteration"] = 1
    atomic_write_json(root / "state.json", state)
    assert run_supervisor(session_id="s1", agent_command="missing", repo_root=repo) == 2
    assert load_json(root / "state.json")["stop_reason"] == "iteration budget exhausted"
    assert not any((root / "iterations").iterdir())
