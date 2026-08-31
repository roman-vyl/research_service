from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.experiments import (
    BatchCandidateRequest,
    BatchCandidateResult,
    BatchExperimentRequest,
    BatchExperimentResult,
    PersistBatchExperiment,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.strategy_instance import DeployableStrategyInstance

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from autoresearch_init import initialize_session  # noqa: E402
from autoresearch_supervisor import (  # noqa: E402
    ContractError,
    _advance_state,
    _journal_event,
    append_journal,
    atomic_write_json,
    load_json,
    run_supervisor,
    validate_iteration_result,
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
    "tested_ranges": [], "promising_regions": [], "rejected_regions": []},
  "side_interpretation": {"aggregate": "aggregate", "long": "long", "short": "short",
    "asymmetry": "long differs from short"},
  "risk_assessment": {"thinning_risk": "explicit thinning risk",
    "temporal_regime_concentration_concern": "explicit concentration concern",
    "other_confounders": ["other confounder"]},
  "conclusion": "one iteration complete",
  "next_discriminating_question": "what next?",
  "proposed_next_experiment": proposed, "hard_stop_reason": hard_reason
}
if mode == "schema_invalid":
    result["unexpected"] = True
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
    assert state["aggregate_interpretation"] == "aggregate"
    assert state["long_interpretation"] == "long"
    assert state["short_interpretation"] == "short"
    assert state["side_asymmetry"] == "long differs from short"
    assert state["thinning_risk"] == "explicit thinning risk"
    assert state["temporal_regime_concentration_concern"] == (
        "explicit concentration concern"
    )
    assert state["other_confounders"] == ["other confounder"]
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
    for name, mode in (
        ("malformed", "malformed"),
        ("schema_invalid", "schema_invalid"),
        ("crash", "crash"),
    ):
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


def _canonical_batch_artifact(
    tmp_path: Path, hashes: tuple[str, ...] = ("market-hash",)
) -> Path:
    request = BatchExperimentRequest(
        experiment_id="exp-1",
        strategy_id="ema_pullback",
        range=ExplicitRange(from_ms=0, to_ms=300_000),
        candidates=tuple(
            BatchCandidateRequest(
                candidate_id=f"c{index}",
                strategy=DeployableStrategyInstance(
                    enabled=True,
                    strategy_id="ema_pullback",
                    ticker="BTCUSDT.P",
                    base_timeframe="5m",
                    raw_spec={"anchor": {"period": 200}},
                ),
                managed_policy_enabled=False,
            )
            for index in range(1, len(hashes) + 1)
        ),
    )
    candidates = tuple(
        BatchCandidateResult(
            candidate_id=f"c{index}",
            run_id=f"run_{index}",
            instance_id=f"ema_pullback:{index}",
            status="completed",
            artifact_path=f"/artifacts/run_{index}",
            realised_trade_count=0,
            open_position_count=0,
            final_equity="10000",
            gross_pnl="0",
            fees_paid="0",
            net_pnl="0",
            market_data_hash=market_hash,
            return_pct="0",
            max_drawdown="0",
            long={"trades": 0, "net_pnl": "0", "return_pct": "0"},
            short={"trades": 0, "net_pnl": "0", "return_pct": "0"},
        )
        for index, market_hash in enumerate(hashes, start=1)
    )
    result = BatchExperimentResult(
        experiment_id="exp-1",
        status="completed",
        candidate_count=len(candidates),
        completed_count=len(candidates),
        failed_count=0,
        candidates=candidates,
    )
    persisted = PersistBatchExperiment(FilesystemArtifactStore(tmp_path / "artifacts")).execute(
        request, result
    )
    return Path(persisted.artifact_path)


def _batch_iteration(artifact: Path) -> dict[str, object]:
    result = _valid_worker_result_for_test()
    result["experiment"] = {
        "kind": "batch",
        "experiment_id": "exp-1",
        "axes": [],
        "candidate_ids": ["c1"],
        "candidate_count": 1,
        "window_policy": {"range_policy": "explicit_range"},
        "strategy_context": {"strategy_id": "ema_pullback"},
        "execution_accounting_assumptions": {},
    }
    result["execution_result"] = {
        "batch_artifact_path": str(artifact),
        "run_ids": ["run_1"],
        "market_data_hash": "market-hash",
        "completed_candidates": 1,
        "failed_candidates": 0,
        "analysis_path": None,
    }
    return result


def _valid_worker_result_for_test() -> dict[str, object]:
    return {
        "contract_version": "bbb_autoresearch_iteration.v1",
        "session_id": "s1",
        "iteration_id": 1,
        "status": "completed",
        "phase": "baseline",
        "hypothesis": "hypothesis",
        "market_property_proxy": "proxy",
        "experiment": {},
        "execution_result": {},
        "observed_response": {
            "topology": "flat",
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


def _session_state(tmp_path: Path) -> dict[str, object]:
    repo, root = _repo(tmp_path)
    assert repo == tmp_path
    return load_json(root / "state.json")


def _validate_test_batch(iteration: dict[str, object], tmp_path: Path) -> None:
    validate_iteration_result(
        iteration,
        _session_state(tmp_path / "repo"),
        artifacts_root=tmp_path / "artifacts",
    )


def test_valid_canonical_batch_artifact_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    monkeypatch.setenv("RESEARCH_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    validate_iteration_result(
        _batch_iteration(artifact), _session_state(tmp_path / "repo")
    )


def test_valid_looking_session_bundle_is_rejected(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    fake = tmp_path / "var/autoresearch/s1/iterations/0001/fake-batch"
    shutil.copytree(artifact, fake)
    with pytest.raises(ContractError, match="canonical path"):
        _validate_test_batch(_batch_iteration(fake), tmp_path)


def test_valid_looking_bundle_outside_artifacts_root_is_rejected(
    tmp_path: Path,
) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    outside = tmp_path / "outside/exp-1"
    shutil.copytree(artifact, outside)
    with pytest.raises(ContractError, match="canonical path"):
        _validate_test_batch(_batch_iteration(outside), tmp_path)


def test_traversal_and_symlink_escape_are_rejected(tmp_path: Path) -> None:
    traversal_root = tmp_path / "traversal"
    artifact = _canonical_batch_artifact(traversal_root)
    traversal = artifact.parent / ".." / "batches" / artifact.name
    with pytest.raises(ContractError, match="traversal"):
        _validate_test_batch(_batch_iteration(traversal), traversal_root)

    symlink_root = tmp_path / "symlink"
    artifact = _canonical_batch_artifact(symlink_root)
    outside = symlink_root / "outside/exp-1"
    shutil.copytree(artifact, outside)
    shutil.rmtree(artifact)
    artifact.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ContractError, match="escapes"):
        _validate_test_batch(_batch_iteration(artifact), symlink_root)


def test_canonical_experiment_path_for_wrong_experiment_is_rejected(
    tmp_path: Path,
) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    iteration = _batch_iteration(artifact)
    iteration["experiment"]["experiment_id"] = "wrong-exp"
    with pytest.raises(ContractError, match="canonical path"):
        _validate_test_batch(iteration, tmp_path)


def test_tampered_batch_summary_is_rejected_by_hash(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    summary = artifact / "summary.json"
    summary.write_bytes(summary.read_bytes() + b"\n")
    with pytest.raises(ContractError, match="sha256"):
        _validate_test_batch(_batch_iteration(artifact), tmp_path)


def test_fake_batch_run_ids_are_rejected(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    iteration = _batch_iteration(artifact)
    iteration["execution_result"]["run_ids"] = ["fake-run"]
    with pytest.raises(ContractError, match="run_ids"):
        _validate_test_batch(iteration, tmp_path)


def test_mismatched_batch_candidate_ids_are_rejected(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    request_path = artifact / "request.json"
    request = json.loads(request_path.read_text())
    request["candidates"][0]["candidate_id"] = "other-candidate"
    request_path.write_text(json.dumps(request))
    with pytest.raises(ContractError, match="candidate IDs"):
        _validate_test_batch(_batch_iteration(artifact), tmp_path)


def test_mismatched_batch_candidate_counts_are_rejected(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    iteration = _batch_iteration(artifact)
    iteration["execution_result"].update(completed_candidates=0, failed_candidates=1)
    with pytest.raises(ContractError, match="counts"):
        _validate_test_batch(iteration, tmp_path)


def test_mismatched_batch_market_data_hash_is_rejected(tmp_path: Path) -> None:
    artifact = _canonical_batch_artifact(tmp_path)
    iteration = _batch_iteration(artifact)
    iteration["execution_result"]["market_data_hash"] = "wrong-hash"
    with pytest.raises(ContractError, match="market_data_hash"):
        _validate_test_batch(iteration, tmp_path)


def test_different_canonical_candidate_market_hashes_are_rejected(
    tmp_path: Path,
) -> None:
    artifact = _canonical_batch_artifact(tmp_path, ("market-hash-a", "market-hash-b"))
    iteration = _batch_iteration(artifact)
    iteration["experiment"].update(candidate_ids=["c1", "c2"], candidate_count=2)
    iteration["execution_result"].update(
        run_ids=["run_1", "run_2"],
        market_data_hash="market-hash-a",
        completed_candidates=2,
    )
    with pytest.raises(ContractError, match="different market_data_hash"):
        _validate_test_batch(iteration, tmp_path)
