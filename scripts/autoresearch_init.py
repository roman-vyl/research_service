#!/usr/bin/env python3
"""Initialize one durable BBB AutoResearch session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from autoresearch_supervisor import (
    REPO_ROOT,
    STATE_VERSION,
    atomic_write_json,
    git_sha,
    session_dir,
    utc_now,
    validate_state,
)


def initialize_session(session_id: str, template_path: Path, repo_root: Path = REPO_ROOT) -> Path:
    root = session_dir(session_id, repo_root)
    if root.exists():
        raise FileExistsError(f"session already exists: {root}")
    try:
        template: dict[str, Any] = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid session template: {exc}") from exc
    now = utc_now()
    state: dict[str, Any] = {
        "contract_version": STATE_VERSION,
        "session_id": session_id,
        "research_program": template["research_program"],
        "skill_path": template["skill_path"],
        "strategy_context": template.get("strategy_context", {}),
        "status": "initialized",
        "baseline_git_sha": git_sha(repo_root),
        "created_at": now,
        "updated_at": now,
        "iteration": 0,
        "phase": template.get("phase", "baseline"),
        "completed_phases": template.get("completed_phases", []),
        "current_hypothesis": template.get("current_hypothesis"),
        "competing_explanations": template.get("competing_explanations", []),
        "findings": template.get("findings", []),
        "structural_dimensions_known": template.get("structural_dimensions_known", []),
        "tested_ranges": template.get("tested_ranges", []),
        "observed_response_shapes": template.get("observed_response_shapes", []),
        "promising_regions": template.get("promising_regions", []),
        "rejected_regions": template.get("rejected_regions", []),
        "aggregate_interpretation": template.get("aggregate_interpretation"),
        "long_interpretation": template.get("long_interpretation"),
        "short_interpretation": template.get("short_interpretation"),
        "side_asymmetry": template.get("side_asymmetry"),
        "thinning_risk": template.get("thinning_risk"),
        "temporal_regime_concentration_concern": template.get(
            "temporal_regime_concentration_concern"
        ),
        "other_confounders": template.get("other_confounders", []),
        "unresolved_questions": template.get("unresolved_questions", []),
        "validation_status": template.get("validation_status"),
        "next_discriminating_question": template.get("next_discriminating_question"),
        "next_experiment": template.get("next_experiment"),
        "last_iteration_result": None,
        "budgets": {
            "max_iterations": template.get("budgets", {}).get("max_iterations"),
            "max_wall_clock_seconds": template.get("budgets", {}).get(
                "max_wall_clock_seconds"
            ),
            "max_consecutive_agent_failures": template.get("budgets", {}).get(
                "max_consecutive_agent_failures", 3
            ),
            "max_candidates_per_iteration": template.get("budgets", {}).get(
                "max_candidates_per_iteration"
            ),
        },
        "stop_reason": None,
    }
    validate_state(state)
    skill = repo_root / state["skill_path"]
    if not skill.is_file():
        raise ValueError(f"domain skill does not exist: {skill}")
    root.mkdir(parents=True, exist_ok=False)
    (root / "iterations").mkdir()
    atomic_write_json(root / "state.json", state)
    (root / "journal.jsonl").touch(exist_ok=False)
    atomic_write_json(
        root / "bootstrap.json",
        {
            "contract_version": "bbb_autoresearch_bootstrap.v1",
            "session_id": session_id,
            "baseline_git_sha": state["baseline_git_sha"],
            "template_path": str(template_path.resolve()),
            "created_at": now,
        },
    )
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args(argv)
    root = initialize_session(args.session, args.template)
    print(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
