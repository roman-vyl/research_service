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
import autoresearch_supervisor as supervisor_module  # noqa: E402
from autoresearch_supervisor import (  # noqa: E402
    ContractError,
    _advance_state,
    _candidate_requires_managed_replay,
    _command_args,
    _freeze_plan,
    _journal_event,
    _materialize_interpretation_identity,
    _session_scoped_experiment_id,
    _sha256,
    _validate_interpretation_binding,
    _with_canonical_experiment_id,
    _with_derived_managed_policy_enabled,
    append_journal,
    atomic_write_json,
    load_json,
    render_interpretation_prompt,
    run_supervisor,
    validate_execution_receipt,
    validate_iteration_result,
)
from autoresearch_quality_contracts import CANONICAL_METRIC_PATHS  # noqa: E402


FAKE_AGENT = r"""#!/usr/bin/env python3
import json
import os
import pathlib
import sys

result_path = pathlib.Path(sys.argv[1])
stage = sys.argv[2]
mode = sys.argv[3]
iteration_id = int(result_path.parent.name)
if mode == "crash":
    raise SystemExit(7)
if mode == "malformed":
    result_path.write_text("{bad json")
    raise SystemExit(0)
if mode == "mutate":
    pathlib.Path("tracked.txt").write_text("changed\n")
if mode == "uv_lock":
    (result_path.parent / "uv.lock").write_text("lock")
if mode == "shim":
    (result_path.parent / "sitecustomize.py").write_text("# shim")
if mode == "py_scratch" and stage == "planning":
    analysis = result_path.parent / "planning_analysis"
    analysis.mkdir(exist_ok=True)
    (analysis / "compute_hash.py").write_text("print('scratch')")
if mode == "market_db":
    (result_path.parent / "market.sqlite3").write_bytes(b"db")
if mode == "mutate_state":
    (result_path.parent.parents[1] / "state.json").write_text("{}")
if mode == "env_probe" and stage == "interpretation":
    analysis = result_path.parent / "interpretation_analysis"
    analysis.mkdir(exist_ok=True)
    (analysis / "env.json").write_text(json.dumps({
      "marker": os.getenv("AUTORESEARCH_TEST_MARKER"), "virtual_env": os.getenv("VIRTUAL_ENV"),
      "path": os.getenv("PATH"), "research_keys": sorted(k for k in os.environ if k.upper().startswith("RESEARCH_"))
    }))

if stage == "planning":
    action = "hard_stop" if mode == "hard_stop" else ("terminal" if mode == "terminal" else ("batch" if mode == "batch" else "artifact_diagnostic"))
    request = None
    if action == "batch":
        request = {"experiment_id": "exp-1", "strategy_id": "ema_pullback",
          "range_policy": "explicit_range", "range": {"from_ms": 0, "to_ms": 300000},
          "description": None, "candidates": [{"candidate_id": "c1",
          "strategy": {"enabled": True, "strategy_id": "ema_pullback", "ticker": "BTCUSDT.P",
          "base_timeframe": "5m", "raw_spec": {"anchor": {"period": 200}}},
          "managed_policy_enabled": False, "execution": {"entry_price_source": "signal_bar_close", "entry_slippage_rate": "0", "protection_anchor": "signal_bar_close"},
          "accounting": {"initial_equity": "10000", "entry_fee_rate": "0", "exit_fee_rate": "0"}, "metadata": {}}]}
    plan = {
      "contract_version": "bbb_autoresearch_execution_plan.v1", "session_id": "s1",
      "iteration_id": iteration_id, "phase": "baseline", "hypothesis": "test hypothesis",
      "question": "what next?", "market_property_proxy": "test proxy",
      "competing_explanation": "alternative", "action": action, "canonical_request": request,
      "explanatory_metadata": {},
      "hard_stop_reason": "contract ambiguity" if action == "hard_stop" else None
    }
    if mode == "env_probe":
        plan["explanatory_metadata"] = {
          "marker": os.getenv("AUTORESEARCH_TEST_MARKER"), "virtual_env": os.getenv("VIRTUAL_ENV"),
          "path": os.getenv("PATH"), "research_keys": sorted(k for k in os.environ if k.upper().startswith("RESEARCH_"))
        }
    if mode == "schema_invalid": plan["unexpected"] = True
    result_path.write_text(json.dumps(plan))
    raise SystemExit(0)

proposed = None
status = "completed"
hard_reason = None
if mode == "continue_then_complete" and iteration_id == 1:
    proposed = {"kind": "artifact_diagnostic", "reason": "next information"}
if mode == "hard_stop":
    status = "hard_stop"
    hard_reason = "contract ambiguity"
if mode == "batch":
    receipt = json.loads((result_path.parent / "execution_receipt.json").read_text())
interp_phase = "baseline"
interp_hypothesis = "test hypothesis"
interp_market_property_proxy = "test proxy"
if mode == "paraphrase":
    interp_hypothesis = "test hypothesis, reworded"
    interp_market_property_proxy = "test proxy restated"
result = {
  "contract_version": "bbb_autoresearch_iteration.v1",
  "session_id": "s1", "iteration_id": iteration_id, "status": status,
  "phase": interp_phase, "hypothesis": interp_hypothesis,
  "market_property_proxy": interp_market_property_proxy,
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
if mode in {"terminal", "hard_stop"}:
    result["experiment"]["kind"] = "none"
if mode == "batch":
    result["experiment"].update(kind="batch", experiment_id=receipt["experiment_id"], candidate_ids=["c1"], candidate_count=1,
      window_policy={"range_policy": "explicit_range"}, execution_accounting_assumptions={})
    result["execution_result"].update(batch_artifact_path=receipt["batch_artifact_path"], run_ids=["run_1"],
      market_data_hash="market-hash", completed_candidates=1)
if mode == "schema_invalid":
    result["unexpected"] = True
result_path.write_text(json.dumps(result))
"""


@pytest.fixture(autouse=True)
def _research_service_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # run_supervisor now resolves the one sanctioned Research Service base URL
    # from the launch profile wrapper's environment before rendering any
    # worker prompt; the test harness plays that role here.
    monkeypatch.setenv("BBB_AUTORESEARCH_RESEARCH_SERVICE_URL", "http://research-service.test")


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "autoresearch/prompts").mkdir(parents=True)
    source_root = Path(__file__).parents[1]
    for name in ("iteration.md", "planning.md", "interpretation.md"):
        prompt = (source_root / "autoresearch/prompts" / name).read_text()
        (tmp_path / "autoresearch/prompts" / name).write_text(prompt)
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
    return f"{sys.executable} {repo / 'fake_agent.py'} {{result_file}} {{stage}} {mode}"


def test_interpretation_prompt_renders_evidence_ref_contract_allowlist(tmp_path: Path) -> None:
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
        "active_stage_binding": {"phase": "baseline", "stage_kind": "descriptive_baseline"},
    }

    prompt = render_interpretation_prompt(state, Path(__file__).parents[1], tmp_path, "batch")

    assert "`canonical_metric`" in prompt
    assert "non-empty `candidate_id`" in prompt
    assert "`iteration_id` and `analysis_path` are forbidden" in prompt
    assert "disguise file evidence as `canonical_metric`" in prompt
    assert "analysis_path` must equal that declared value exactly" in prompt
    rendered_allowlist = prompt.split(
        "Allowed canonical metric paths (rendered from the current contract layer):\n", 1
    )[1].split("\n\n", 1)[0]
    assert {item.strip("`") for item in rendered_allowlist.split(", ")} == set(
        CANONICAL_METRIC_PATHS
    )


def test_interpretation_prompt_allowlist_uses_contract_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        supervisor_module, "CANONICAL_METRIC_PATHS", frozenset({"contract.probe"})
    )
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
        "active_stage_binding": {"phase": "baseline", "stage_kind": "descriptive_baseline"},
    }

    prompt = render_interpretation_prompt(state, Path(__file__).parents[1], tmp_path, "batch")

    assert "`contract.probe`" in prompt


def test_interpretation_prompt_renders_stage_metric_role_contract_for_baseline(
    tmp_path: Path,
) -> None:
    # Regression: interpretation left stage.metric_roles.primary empty for
    # descriptive_baseline (3/3 attempts, identical hard-stop) because
    # nothing told the worker what validate_metric_roles enforces for the
    # first stage.
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
        "active_stage_binding": {"phase": "baseline", "stage_kind": "descriptive_baseline"},
    }

    prompt = render_interpretation_prompt(state, Path(__file__).parents[1], tmp_path, "batch")

    assert "Stage: descriptive_baseline" in prompt
    assert "primary must include realised_trade_count." in prompt
    assert "promotion_gates must be empty at this stage." in prompt


def test_interpretation_prompt_renders_stage_metric_role_contract_for_v3_session(
    tmp_path: Path,
) -> None:
    # The original fix only rendered this for contract_version v2; v3
    # sessions (the current AutoResearch default) must get it too.
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v3",
        "active_stage": "A_BASELINE",
        "active_stage_binding": {"phase": "baseline", "stage_kind": "descriptive_baseline"},
        "stage_contract": None,
        "phase_a_references": [],
        "stage_dispositions": [],
    }

    prompt = render_interpretation_prompt(state, Path(__file__).parents[1], tmp_path, "batch")

    assert "Stage: descriptive_baseline" in prompt
    assert "primary must include realised_trade_count." in prompt


def test_interpretation_prompt_names_execution_receipt_as_experiment_id_authority(
    tmp_path: Path,
) -> None:
    # Regression for the double-prefix contract defect: after freeze,
    # execution_plan.json is no longer authoritative for the executed
    # experiment_id, only the execution receipt is. The worker must be told
    # this explicitly, not left to infer it.
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
        "active_stage_binding": {"phase": "baseline", "stage_kind": "descriptive_baseline"},
    }
    iteration_root = tmp_path
    receipt_path = iteration_root / "execution_receipt.json"

    prompt = render_interpretation_prompt(state, Path(__file__).parents[1], iteration_root, "batch")

    assert "experiment.experiment_id" in prompt
    assert str(receipt_path) in prompt
    assert "no longer authoritative" in prompt
    assert "Never compute, reconstruct, or otherwise derive this value yourself." in prompt

    non_batch_prompt = render_interpretation_prompt(
        state, Path(__file__).parents[1], iteration_root, "artifact_diagnostic"
    )
    assert "must be copied verbatim from" not in non_batch_prompt


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
    assert state["temporal_regime_concentration_concern"] == ("explicit concentration concern")
    assert state["other_confounders"] == ["other confounder"]
    assert (root / "iterations/0001/planning.stdout.log").is_file()
    assert (root / "iterations/0001/interpretation.stdout.log").is_file()
    assert (root / "iterations/0002/planning.stdout.log").is_file()
    assert len((root / "journal.jsonl").read_text().splitlines()) == 2


def test_restart_resumes_at_next_iteration(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    seed_path = root / "seed/0001/iteration_result.json"
    seed_path.parent.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            str(repo / "fake_agent.py"),
            str(seed_path),
            "interpretation",
            "continue_then_complete",
        ],
        cwd=repo,
        check=True,
    )
    first_result = json.loads(seed_path.read_text())
    append_journal(root / "journal.jsonl", _journal_event(state, first_result))
    atomic_write_json(root / "state.json", _advance_state(state, first_result))

    assert (
        run_supervisor(
            session_id="s1", agent_command=_command(repo, "continue_then_complete"), repo_root=repo
        )
        == 0
    )
    assert load_json(root / "state.json")["iteration"] == 2
    assert not (root / "iterations/0001").exists()
    assert (root / "iterations/0002").exists()


def test_hard_stop_result_launches_no_next_worker(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(session_id="s1", agent_command=_command(repo, "hard_stop"), repo_root=repo)
        == 2
    )
    assert load_json(root / "state.json")["status"] == "hard_stopped"
    assert not (root / "iterations/0002").exists()


@pytest.mark.parametrize("mode", ["continue_then_complete", "terminal", "hard_stop"])
def test_non_batch_actions_use_fresh_interpreter_without_executor_or_receipt(
    tmp_path: Path, mode: str
) -> None:
    repo, root = _repo(tmp_path)
    code = run_supervisor(
        session_id="s1", agent_command=_command(repo, mode), repo_root=repo, max_iterations=1
    )
    assert code in {0, 2}
    iteration = root / "iterations/0001"
    metadata = load_json(iteration / "supervisor_metadata.json")
    assert len(metadata["planning_attempts"]) == 1
    assert len(metadata["interpretation_attempts"]) == 1
    assert not (iteration / "execution_receipt.json").exists()
    assert not (iteration / "execution_output.json").exists()
    assert not (iteration / "executor.stdout.log").exists()
    assert len((root / "journal.jsonl").read_text().splitlines()) == 1


def test_worker_env_preserves_cli_runtime_and_removes_research_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, root = _repo(tmp_path)
    monkeypatch.setenv("AUTORESEARCH_TEST_MARKER", "visible")
    monkeypatch.setenv("VIRTUAL_ENV", "/provider/venv")
    monkeypatch.setenv("RESEARCH_STRATEGY_ENGINE_URL", "http://secret-engine")
    monkeypatch.setenv("RESEARCH_MARKET_DATA_URL", "http://secret-mds")
    monkeypatch.setenv("RESEARCH_ARTIFACTS_ROOT", "/secret/artifacts")
    monkeypatch.setenv("RESEARCH_CONFIGS_ROOT", "/secret/configs")
    monkeypatch.setenv("RESEARCH_FUTURE_EXECUTION_SETTING", "secret")
    assert (
        run_supervisor(
            session_id="s1",
            agent_command=_command(repo, "env_probe"),
            repo_root=repo,
            max_iterations=1,
        )
        == 0
    )
    planning = load_json(root / "iterations/0001/execution_plan.json")["explanatory_metadata"]
    interpretation = load_json(root / "iterations/0001/interpretation_analysis/env.json")
    for observed in (planning, interpretation):
        assert observed["marker"] == "visible"
        assert observed["virtual_env"] == "/provider/venv"
        assert observed["path"]
        assert observed["research_keys"] == []


def test_supervisor_owned_batch_flow_creates_and_binds_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, root = _repo(tmp_path / "repo")
    artifacts_root = tmp_path / "artifacts"
    # FAKE_AGENT's plan uses logical experiment_id "exp-1" for session "s1";
    # the supervisor session-scopes it to "s1-exp-1" before freezing.
    artifact = _canonical_batch_artifact(tmp_path, experiment_id="s1-exp-1")
    assert artifact == artifacts_root / "batches/s1-exp-1"
    monkeypatch.setenv("RESEARCH_ARTIFACTS_ROOT", str(artifacts_root))
    monkeypatch.setenv("RESEARCH_CONFIGS_ROOT", str(tmp_path / "configs"))
    monkeypatch.setenv("RESEARCH_STRATEGY_ENGINE_URL", "http://canonical-engine")
    monkeypatch.setenv("RESEARCH_MARKET_DATA_URL", "http://canonical-mds")
    monkeypatch.setenv("RESEARCH_UNKNOWN_EXECUTION_OVERRIDE", "must-not-pass")
    original_run = supervisor_module.subprocess.run
    observed_executor_env: dict[str, str] = {}

    def fake_run(args, *positional, **kwargs):
        if isinstance(args, list) and any(
            str(item).endswith("scripts/autoresearch_execute_batch.py") for item in args
        ):
            observed_executor_env.update(kwargs["env"])
            output_path = Path(args[args.index("--output") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "contract_version": "bbb_autoresearch_batch_execution.v1",
                        "request_contract_version": "research_batch_experiment.v1",
                        "result": json.loads((artifact / "summary.json").read_text()),
                        "persisted_batch": {"artifact_path": str(artifact)},
                    }
                )
            )
            return subprocess.CompletedProcess(args, 0)
        return original_run(args, *positional, **kwargs)

    monkeypatch.setattr(supervisor_module.subprocess, "run", fake_run)
    initial_state = load_json(root / "state.json")
    assert (
        run_supervisor(
            session_id="s1", agent_command=_command(repo, "batch"), repo_root=repo, max_iterations=1
        )
        == 0
    )
    iteration = root / "iterations/0001"
    receipt = load_json(iteration / "execution_receipt.json")
    assert receipt["experiment_id"] == "s1-exp-1"
    assert receipt["candidate_ids"] == ["c1"]
    assert receipt["batch_artifact_path"] == str(artifact)
    assert observed_executor_env["RESEARCH_STRATEGY_ENGINE_URL"] == "http://canonical-engine"
    assert observed_executor_env["RESEARCH_MARKET_DATA_URL"] == "http://canonical-mds"
    assert observed_executor_env["RESEARCH_ARTIFACTS_ROOT"] == str(artifacts_root)
    assert observed_executor_env["RESEARCH_CONFIGS_ROOT"] == str(tmp_path / "configs")
    assert "RESEARCH_UNKNOWN_EXECUTION_OVERRIDE" not in observed_executor_env
    assert load_json(iteration / "iteration_control.json")["stage"] == "committed"
    assert len((root / "journal.jsonl").read_text().splitlines()) == 1
    plan = load_json(iteration / "execution_plan.json")
    bad_receipt = dict(receipt)
    bad_receipt["adapter_output_sha256"] = "0" * 64
    with pytest.raises(ContractError, match="adapter_output_sha256"):
        validate_execution_receipt(
            bad_receipt,
            plan,
            initial_state,
            iteration / "canonical_request.json",
            iteration / "execution_output.json",
        )


def test_resume_frozen_non_batch_plan_skips_planning_and_executor(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    plan = {
        "contract_version": "bbb_autoresearch_execution_plan.v1",
        "session_id": "s1",
        "iteration_id": 1,
        "phase": "baseline",
        "hypothesis": "test hypothesis",
        "question": "what next?",
        "market_property_proxy": "test proxy",
        "competing_explanation": "alternative",
        "action": "terminal",
        "canonical_request": None,
        "explanatory_metadata": {},
        "hard_stop_reason": None,
    }
    _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    assert (
        run_supervisor(session_id="s1", agent_command=_command(repo, "terminal"), repo_root=repo)
        == 0
    )
    metadata = load_json(iteration / "supervisor_metadata.json")
    assert metadata["planning_attempts"] == []
    assert len(metadata["interpretation_attempts"]) == 1
    assert not (iteration / "execution_receipt.json").exists()
    assert not (iteration / "executor.stdout.log").exists()


def test_pre_brokered_session_is_not_silently_migrated(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    bootstrap = load_json(root / "bootstrap.json")
    bootstrap.pop("execution_protocol")
    atomic_write_json(root / "bootstrap.json", bootstrap)
    assert (
        run_supervisor(session_id="s1", agent_command=_command(repo, "terminal"), repo_root=repo)
        == 2
    )
    assert "predates supervisor-brokered execution" in load_json(root / "state.json")["stop_reason"]
    assert not any((root / "iterations").iterdir())


def test_recover_prepared_non_batch_interpretation_commits_without_worker(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    plan = {
        "contract_version": "bbb_autoresearch_execution_plan.v1",
        "session_id": "s1",
        "iteration_id": 1,
        "phase": "baseline",
        "hypothesis": "test hypothesis",
        "question": "what next?",
        "market_property_proxy": "test proxy",
        "competing_explanation": "alternative",
        "action": "terminal",
        "canonical_request": None,
        "explanatory_metadata": {},
        "hard_stop_reason": None,
    }
    control = _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    subprocess.run(
        [
            sys.executable,
            str(repo / "fake_agent.py"),
            str(iteration / "iteration_result.json"),
            "interpretation",
            "terminal",
        ],
        cwd=repo,
        check=True,
    )
    control.update(
        stage="interpretation_prepared",
        interpretation_sha256=_sha256(iteration / "iteration_result.json"),
    )
    atomic_write_json(iteration / "iteration_control.json", control)
    assert run_supervisor(session_id="s1", agent_command="definitely-missing", repo_root=repo) == 0
    assert len((root / "journal.jsonl").read_text().splitlines()) == 1
    assert load_json(root / "state.json")["iteration"] == 1
    assert not (iteration / "supervisor_metadata.json").exists()


def test_recover_completed_batch_output_does_not_rerun_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, root = _repo(tmp_path / "repo")
    state = load_json(root / "state.json")
    # FAKE_AGENT's plan uses logical experiment_id "exp-1" for session "s1";
    # the supervisor session-scopes it to "s1-exp-1" before freezing.
    artifact = _canonical_batch_artifact(tmp_path, experiment_id="s1-exp-1")
    monkeypatch.setenv("RESEARCH_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            str(repo / "fake_agent.py"),
            str(iteration / "execution_plan.json"),
            "planning",
            "batch",
        ],
        cwd=repo,
        check=True,
    )
    plan = load_json(iteration / "execution_plan.json")
    control = _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    control["execution_intent"] = {
        "started_at": "2026-01-01T00:00:00+00:00",
        "request_sha256": control["request_sha256"],
    }
    atomic_write_json(iteration / "iteration_control.json", control)
    atomic_write_json(
        iteration / "execution_output.json",
        {
            "contract_version": "bbb_autoresearch_batch_execution.v1",
            "request_contract_version": "research_batch_experiment.v1",
            "result": json.loads((artifact / "summary.json").read_text()),
            "persisted_batch": {"artifact_path": str(artifact)},
        },
    )
    original_run = supervisor_module.subprocess.run
    executor_calls = 0

    def forbid_executor(args, *positional, **kwargs):
        nonlocal executor_calls
        if isinstance(args, list) and any(
            str(item).endswith("scripts/autoresearch_execute_batch.py") for item in args
        ):
            executor_calls += 1
            raise AssertionError("executor must not rerun")
        return original_run(args, *positional, **kwargs)

    monkeypatch.setattr(supervisor_module.subprocess, "run", forbid_executor)
    assert (
        run_supervisor(session_id="s1", agent_command=_command(repo, "batch"), repo_root=repo) == 0
    )
    assert executor_calls == 0
    assert (iteration / "execution_receipt.json").is_file()
    assert len((root / "journal.jsonl").read_text().splitlines()) == 1


@pytest.mark.parametrize("provider", ["codex exec -", "claude -p"])
def test_provider_commands_share_generic_stage_contract(provider: str) -> None:
    args = _command_args(
        provider + " {stage} {result_file}",
        {"stage": "planning", "result_file": "/tmp/result.json"},
    )
    assert args[-2:] == ["planning", "/tmp/result.json"]


def test_forbidden_mutation_hard_stops_and_preserves_evidence(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(session_id="s1", agent_command=_command(repo, "mutate"), repo_root=repo) == 2
    )
    assert (repo / "tracked.txt").read_text() == "changed\n"
    assert "tracked.txt" in load_json(root / "state.json")["stop_reason"]


@pytest.mark.parametrize(
    "mode,filename",
    [("uv_lock", "uv.lock"), ("shim", "sitecustomize.py"), ("market_db", "market.sqlite3")],
)
def test_stage_output_boundary_rejects_dependency_shim_and_raw_db(
    tmp_path: Path, mode: str, filename: str
) -> None:
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(
            session_id="s1",
            agent_command=_command(repo, mode),
            repo_root=repo,
            max_agent_failures=1,
        )
        == 2
    )
    assert (root / "iterations/0001" / filename).exists()
    assert "output boundary violation" in load_json(root / "state.json")["stop_reason"]


def test_planning_output_boundary_still_rejects_python_scratch_files(tmp_path: Path) -> None:
    # Regression guard for the geometry_references fix: the harness contract
    # bug is fixed by publishing sanctioned per-geometry hashes into state,
    # not by loosening what a planning worker is allowed to write. A worker
    # that still writes a .py scratch file under planning_analysis/ (e.g. to
    # try computing a hash itself) must still be hard-stopped exactly as
    # before.
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(
            session_id="s1",
            agent_command=_command(repo, "py_scratch"),
            repo_root=repo,
            max_agent_failures=1,
        )
        == 2
    )
    assert (root / "iterations/0001/planning_analysis/compute_hash.py").exists()
    stop_reason = load_json(root / "state.json")["stop_reason"]
    assert "output boundary violation" in stop_reason
    assert "planning_analysis/compute_hash.py" in stop_reason


def test_worker_cannot_modify_durable_session_state(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(
            session_id="s1",
            agent_command=_command(repo, "mutate_state"),
            repo_root=repo,
            max_agent_failures=1,
        )
        == 2
    )
    assert "state.json" in load_json(root / "state.json")["stop_reason"]


def test_malformed_result_and_crash_retry_are_bounded(tmp_path: Path) -> None:
    for name, mode in (
        ("malformed", "malformed"),
        ("schema_invalid", "schema_invalid"),
        ("crash", "crash"),
    ):
        repo, root = _repo(tmp_path / name)
        assert (
            run_supervisor(
                session_id="s1",
                agent_command=_command(repo, mode),
                repo_root=repo,
                max_agent_failures=2,
            )
            == 2
        )
        metadata = load_json(root / "iterations/0001/supervisor_metadata.json")
        assert len(metadata["planning_attempts"]) + len(metadata["interpretation_attempts"]) == 2
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
    tmp_path: Path, hashes: tuple[str, ...] = ("market-hash",), *, experiment_id: str = "exp-1"
) -> Path:
    request = BatchExperimentRequest(
        experiment_id=experiment_id,
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
        experiment_id=experiment_id,
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


def _batch_plan(strategy_raw_spec: dict[str, object], *, worker_managed_policy_enabled: bool) -> dict[str, object]:
    return {
        "contract_version": "bbb_autoresearch_execution_plan.v1",
        "session_id": "s1",
        "iteration_id": 1,
        "phase": "baseline",
        "hypothesis": "test hypothesis",
        "question": "what next?",
        "market_property_proxy": "test proxy",
        "competing_explanation": "alternative",
        "action": "batch",
        "canonical_request": {
            "experiment_id": "exp-1",
            "strategy_id": "ema_pullback",
            "range_policy": "explicit_range",
            "range": {"from_ms": 0, "to_ms": 300000},
            "description": None,
            "candidates": [
                {
                    "candidate_id": "c1",
                    "strategy": {
                        "enabled": True,
                        "strategy_id": "ema_pullback",
                        "ticker": "BTCUSDT.P",
                        "base_timeframe": "5m",
                        "raw_spec": strategy_raw_spec,
                    },
                    "managed_policy_enabled": worker_managed_policy_enabled,
                    "execution": {
                        "entry_price_source": "signal_bar_close",
                        "entry_slippage_rate": "0",
                        "protection_anchor": "signal_bar_close",
                    },
                    "accounting": {
                        "initial_equity": "10000",
                        "entry_fee_rate": "0",
                        "exit_fee_rate": "0",
                    },
                    "metadata": {},
                }
            ],
        },
        "explanatory_metadata": {},
        "hard_stop_reason": None,
    }


def test_candidate_requires_managed_replay_is_false_for_naked_exit_management() -> None:
    plan = _batch_plan(
        {"trade_management": {"exit_management": {}}}, worker_managed_policy_enabled=True
    )
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    assert _candidate_requires_managed_replay(request.candidates[0]) is False


def test_candidate_requires_managed_replay_is_true_for_explicit_managed_mode() -> None:
    plan = _batch_plan(
        {"trade_management": {"exit_management": {"mode": "managed"}}},
        worker_managed_policy_enabled=False,
    )
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    assert _candidate_requires_managed_replay(request.candidates[0]) is True


def test_with_derived_managed_policy_enabled_overrides_worker_value() -> None:
    # Worker wrote managed_policy_enabled=True for a naked (non-managed)
    # candidate -- the derived value must win regardless.
    plan = _batch_plan(
        {"trade_management": {"exit_management": {}}}, worker_managed_policy_enabled=True
    )
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    derived = _with_derived_managed_policy_enabled(request)
    assert derived.candidates[0].managed_policy_enabled is False

    # And the reverse: worker wrote False for a genuinely managed candidate.
    plan = _batch_plan(
        {"trade_management": {"exit_management": {"mode": "managed"}}},
        worker_managed_policy_enabled=False,
    )
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    derived = _with_derived_managed_policy_enabled(request)
    assert derived.candidates[0].managed_policy_enabled is True


def test_freeze_plan_writes_explicit_managed_policy_enabled_for_naked_candidate(
    tmp_path: Path,
) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    # The worker plan omits exit_management.mode (naked baseline fixture
    # shape) and leaves managed_policy_enabled unset in its own JSON --
    # Pydantic's bare `BatchCandidateRequest.managed_policy_enabled` default
    # is True, so an unmodified freeze would silently inherit that default.
    plan = _batch_plan(
        {
            "anchor_stack": {"anchor": {"period": 200}},
            "trade_management": {"exit_management": {}},
        },
        worker_managed_policy_enabled=True,
    )
    _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    frozen = load_json(iteration / "canonical_request.json")
    assert frozen["candidates"][0]["managed_policy_enabled"] is False


def test_session_scoped_experiment_id_differs_across_sessions_for_same_logical_id() -> None:
    # The harness contract bug: two independent sessions whose planning
    # workers both pick the same readable logical experiment_id must never
    # collide on canonical batch storage.
    first = _session_scoped_experiment_id("session-one", "a-baseline-geometry-a2")
    second = _session_scoped_experiment_id("session-two", "a-baseline-geometry-a2")
    assert first != second
    assert first == "session-one-a-baseline-geometry-a2"
    assert second == "session-two-a-baseline-geometry-a2"


def test_session_scoped_experiment_id_is_deterministic_within_a_session() -> None:
    first = _session_scoped_experiment_id("session-one", "a-baseline-geometry-a2")
    second = _session_scoped_experiment_id("session-one", "a-baseline-geometry-a2")
    assert first == second


def test_session_scoped_experiment_id_is_idempotent_for_a_self_namespaced_logical_id() -> None:
    # Regression for the double-prefix contract defect observed in a
    # controlled HOST smoke: a planning worker that independently decided
    # to include the session_id in its own "logical" experiment_id (e.g.
    # "smoke-v3-2026-09-03f-i0001-a-baseline-a2") must not be scoped again
    # on top -- scoping the already-scoped result must be a no-op.
    session_id = "smoke-v3-2026-09-03f"
    self_namespaced_logical_id = f"{session_id}-i0001-a-baseline-a2"
    once = _session_scoped_experiment_id(session_id, self_namespaced_logical_id)
    assert once == self_namespaced_logical_id
    twice = _session_scoped_experiment_id(session_id, once)
    assert twice == once


def test_session_scoped_experiment_id_idempotency_does_not_weaken_cross_session_uniqueness() -> None:
    # Idempotency must not come at the cost of collision protection: a
    # logical id that happens to already start with a *different* session's
    # prefix is still scoped normally under the current session.
    logical_id = "session-a-a-baseline-a2"
    scoped_under_a = _session_scoped_experiment_id("session-a", logical_id)
    scoped_under_b = _session_scoped_experiment_id("session-b", logical_id)
    assert scoped_under_a == logical_id
    assert scoped_under_b == "session-b-session-a-a-baseline-a2"
    assert scoped_under_a != scoped_under_b


def test_with_canonical_experiment_id_is_idempotent() -> None:
    plan = _batch_plan(
        {"trade_management": {"exit_management": {}}}, worker_managed_policy_enabled=False
    )
    plan["canonical_request"]["experiment_id"] = "s1-exp-1"
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    scoped_once = _with_canonical_experiment_id(request, "s1")
    scoped_twice = _with_canonical_experiment_id(scoped_once, "s1")
    assert scoped_once.experiment_id == "s1-exp-1"
    assert scoped_twice.experiment_id == "s1-exp-1"


def test_with_canonical_experiment_id_scopes_request_without_dropping_logical_label() -> None:
    plan = _batch_plan(
        {"trade_management": {"exit_management": {}}}, worker_managed_policy_enabled=False
    )
    request = BatchExperimentRequest.model_validate(plan["canonical_request"])
    assert request.experiment_id == "exp-1"
    scoped = _with_canonical_experiment_id(request, "s1")
    assert scoped.experiment_id == "s1-exp-1"
    # The worker's logical label is preserved verbatim, recoverable by
    # stripping the known session_id prefix -- never silently discarded.
    assert scoped.experiment_id.removeprefix("s1-") == request.experiment_id


def _identity_plan(**overrides: object) -> dict[str, object]:
    plan = {
        "phase": "baseline",
        "hypothesis": "test hypothesis",
        "market_property_proxy": "test proxy",
    }
    plan.update(overrides)
    return plan


def _identity_result(**overrides: object) -> dict[str, object]:
    result = {
        "phase": "baseline",
        "hypothesis": "test hypothesis",
        "market_property_proxy": "test proxy",
        "conclusion": "worker's own conclusion",
        "next_discriminating_question": "worker's own next question",
    }
    result.update(overrides)
    return result


def test_materialize_interpretation_identity_overrides_worker_paraphrase() -> None:
    # Regression for the interpretation-binding contract defect: a worker
    # that retypes the frozen hypothesis/market_property_proxy from memory
    # (punctuation/wording drift, not a scientific disagreement) must be
    # healed deterministically rather than rejected for typing infidelity.
    plan = _identity_plan(
        hypothesis="target, and every later structural claim must be explained relative to it.",
        market_property_proxy="No structural market-state proxy is being tested yet.",
    )
    result = _identity_result(
        hypothesis="target; every later structural claim must be explained relative to it.",
        market_property_proxy="No structural market-state proxy tested.",
    )
    materialized = _materialize_interpretation_identity(result, plan)
    assert materialized["hypothesis"] == plan["hypothesis"]
    assert materialized["market_property_proxy"] == plan["market_property_proxy"]
    assert materialized["phase"] == plan["phase"]


def test_materialize_interpretation_identity_leaves_worker_owned_fields_untouched() -> None:
    plan = _identity_plan()
    result = _identity_result(
        conclusion="a specific worker conclusion",
        next_discriminating_question="a specific worker question",
    )
    materialized = _materialize_interpretation_identity(result, plan)
    assert materialized["conclusion"] == "a specific worker conclusion"
    assert materialized["next_discriminating_question"] == "a specific worker question"


def test_validate_interpretation_binding_still_rejects_true_identity_mismatch() -> None:
    # The equality check stays a fail-closed invariant: something that
    # bypasses materialization (or a future code path that forgets to call
    # it) must still be caught, not silently accepted.
    plan = _identity_plan()
    result = _identity_result(hypothesis="a genuinely different scientific hypothesis")
    with pytest.raises(ContractError, match="differs from frozen plan identity"):
        _validate_interpretation_binding(result, plan, {}, Path("."))


def test_interpretation_paraphrase_is_healed_end_to_end(tmp_path: Path) -> None:
    # A worker that paraphrases phase/hypothesis/market_property_proxy must
    # no longer hard-stop the session -- materialization heals it before
    # the result is validated and frozen.
    repo, root = _repo(tmp_path)
    assert (
        run_supervisor(
            session_id="s1", agent_command=_command(repo, "paraphrase"), repo_root=repo
        )
        == 0
    )
    iteration = root / "iterations/0001"
    frozen = load_json(iteration / "iteration_result.json")
    assert frozen["hypothesis"] == "test hypothesis"
    assert frozen["market_property_proxy"] == "test proxy"
    assert load_json(root / "state.json")["iteration"] == 1


def test_freeze_plan_writes_session_scoped_canonical_experiment_id(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    assert state["session_id"] == "s1"
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    plan = _batch_plan(
        {"trade_management": {"exit_management": {}}}, worker_managed_policy_enabled=False
    )
    assert plan["canonical_request"]["experiment_id"] == "exp-1"
    _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    frozen = load_json(iteration / "canonical_request.json")
    assert frozen["experiment_id"] == "s1-exp-1"


def test_same_logical_experiment_id_in_different_sessions_produces_coexisting_artifacts(
    tmp_path: Path,
) -> None:
    # Both artifact paths must coexist; neither write may overwrite the
    # other, and nothing is deleted to make room.
    first = _canonical_batch_artifact(
        tmp_path / "one", experiment_id=_session_scoped_experiment_id("session-one", "exp-1")
    )
    second = _canonical_batch_artifact(
        tmp_path / "one", experiment_id=_session_scoped_experiment_id("session-two", "exp-1")
    )
    assert first != second
    assert first.is_dir()
    assert second.is_dir()
    assert (first / "summary.json").is_file()
    assert (second / "summary.json").is_file()


def test_same_session_and_logical_experiment_id_collision_still_fails_closed(
    tmp_path: Path,
) -> None:
    # Collision protection within one session must not be bypassed by the
    # session-scoping fix: reusing the same canonical (session + logical)
    # experiment_id still raises rather than overwriting.
    canonical_id = _session_scoped_experiment_id("s1", "exp-1")
    _canonical_batch_artifact(tmp_path, experiment_id=canonical_id)
    with pytest.raises(FileExistsError, match=canonical_id):
        _canonical_batch_artifact(tmp_path, experiment_id=canonical_id)


def test_freeze_plan_writes_explicit_managed_policy_enabled_for_managed_candidate(
    tmp_path: Path,
) -> None:
    repo, root = _repo(tmp_path)
    state = load_json(root / "state.json")
    iteration = root / "iterations/0001"
    iteration.mkdir(parents=True)
    plan = _batch_plan(
        {
            "anchor_stack": {"anchor": {"period": 200}},
            "trade_management": {"exit_management": {"mode": "managed"}},
        },
        worker_managed_policy_enabled=False,
    )
    _freeze_plan(
        iteration / "execution_plan.json", iteration / "iteration_control.json", plan, state
    )
    frozen = load_json(iteration / "canonical_request.json")
    assert frozen["candidates"][0]["managed_policy_enabled"] is True


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
    validate_iteration_result(_batch_iteration(artifact), _session_state(tmp_path / "repo"))


_ITERATION_RESULT_SCHEMA_FILES = (
    "iteration_result.schema.json",
    "iteration_result.v2.schema.json",
    "iteration_result.v3.schema.json",
)

# (top-level `iteration_result` property name, matching supervisor exact-keys
# constant) for every nested object the supervisor validates with
# `_require_exact_keys` -- kept in one place so the parity guard below covers
# every one of them, not just `experiment`.
_NESTED_OBJECT_FIELDS = (
    ("experiment", "_EXPERIMENT_KEYS"),
    ("execution_result", "_EXECUTION_RESULT_KEYS"),
    ("observed_response", "_OBSERVED_RESPONSE_KEYS"),
    ("side_interpretation", "_SIDE_INTERPRETATION_KEYS"),
    ("risk_assessment", "_RISK_ASSESSMENT_KEYS"),
)


def _nested_object_schema_shape(schema_filename: str, field_name: str) -> dict[str, object]:
    schema_path = Path(__file__).parents[1] / "autoresearch/schemas" / schema_filename
    schema = json.loads(schema_path.read_text())
    shape = schema["properties"][field_name]
    if "$ref" in shape:
        ref = shape["$ref"].removeprefix("#/$defs/")
        shape = schema["$defs"][ref]
    return shape


def test_experiment_schema_required_keys_match_supervisor_exact_keys() -> None:
    # Anti-divergence guard for the harness contract bug: the schema each
    # interpretation worker is told to conform to, and the supervisor's own
    # runtime `_require_exact_keys(experiment, _EXPERIMENT_KEYS, ...)` check,
    # must declare the exact same `experiment` field set. If either changes
    # without the other, this test catches it before a worker does.
    for schema_filename in _ITERATION_RESULT_SCHEMA_FILES:
        experiment = _nested_object_schema_shape(schema_filename, "experiment")
        assert experiment.get("additionalProperties") is False, schema_filename
        assert set(experiment["required"]) == supervisor_module._EXPERIMENT_KEYS, schema_filename
        assert set(experiment["properties"]) == supervisor_module._EXPERIMENT_KEYS, schema_filename


def test_all_nested_result_objects_schema_matches_supervisor_exact_keys() -> None:
    # Same guard as above, generalized to every other iteration_result nested
    # object the supervisor enforces exact keys on -- execution_result,
    # observed_response, side_interpretation, risk_assessment previously had
    # the same bare-{"type": "object"} regression in the v3 schema as
    # experiment did.
    for field_name, keys_attr in _NESTED_OBJECT_FIELDS:
        expected = getattr(supervisor_module, keys_attr)
        for schema_filename in _ITERATION_RESULT_SCHEMA_FILES:
            shape = _nested_object_schema_shape(schema_filename, field_name)
            assert shape.get("additionalProperties") is False, (schema_filename, field_name)
            assert set(shape["required"]) == expected, (schema_filename, field_name)
            assert set(shape["properties"]) == expected, (schema_filename, field_name)


def test_canonical_experiment_shape_is_accepted(tmp_path: Path) -> None:
    result = _valid_worker_result_for_test()
    result["experiment"] = {
        "kind": "none",
        "experiment_id": None,
        "axes": [],
        "candidate_ids": [],
        "candidate_count": 0,
        "window_policy": None,
        "strategy_context": {"strategy_id": "ema_pullback"},
        "execution_accounting_assumptions": None,
    }
    result["execution_result"] = {
        "batch_artifact_path": None,
        "run_ids": [],
        "market_data_hash": None,
        "completed_candidates": 0,
        "failed_candidates": 0,
        "analysis_path": None,
    }
    validate_iteration_result(result, _session_state(tmp_path / "repo"))


def test_experiment_missing_required_field_is_rejected(tmp_path: Path) -> None:
    result = _valid_worker_result_for_test()
    result["experiment"] = {
        "kind": "none",
        "experiment_id": None,
        "axes": [],
        "candidate_ids": [],
        "candidate_count": 0,
        "window_policy": None,
        "strategy_context": {"strategy_id": "ema_pullback"},
        # execution_accounting_assumptions omitted
    }
    with pytest.raises(ContractError, match="experiment fields differ"):
        validate_iteration_result(result, _session_state(tmp_path / "repo"))


def test_experiment_extra_field_is_rejected(tmp_path: Path) -> None:
    result = _valid_worker_result_for_test()
    result["experiment"] = {
        "kind": "none",
        "experiment_id": None,
        "axes": [],
        "candidate_ids": [],
        "candidate_count": 0,
        "window_policy": None,
        "strategy_context": {"strategy_id": "ema_pullback"},
        "execution_accounting_assumptions": None,
        "geometry_id": "A-2",
    }
    with pytest.raises(ContractError, match="experiment fields differ"):
        validate_iteration_result(result, _session_state(tmp_path / "repo"))


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
