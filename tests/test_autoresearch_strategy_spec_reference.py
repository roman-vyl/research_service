"""Regression coverage for the AutoResearch Strategy Specification Reference.

Proves: (1) the reference document exists and points to the sanctioned Research
component catalog rather than direct Strategy Engine/MDS discovery; (2) the one
centralized pointer to it (in `program.md`, read by every worker entry point) is
present; (3) every fresh-worker entry point still reads `program.md` (and
therefore inherits the pointer) after this change, regardless of which stage it
starts at.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
REFERENCE_PATH = REPO_ROOT / "autoresearch/references/strategy_specification_reference.md"
PROGRAM_PATH = REPO_ROOT / "autoresearch/program.md"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from autoresearch_supervisor import (  # noqa: E402
    render_interpretation_prompt,
    render_planning_prompt,
)


def test_reference_document_exists_and_is_navigation_not_a_second_contract() -> None:
    text = REFERENCE_PATH.read_text(encoding="utf-8")
    assert "navigation" in text.lower()
    assert "not a second contract" in text.lower()


def test_reference_points_to_sanctioned_component_catalog_not_direct_engine_access() -> None:
    text = REFERENCE_PATH.read_text(encoding="utf-8")
    assert "GET /api/research/component-catalog" in text
    assert "POST /api/research/config/validate" in text
    # Must not embed a direct Engine/MDS base URL or port -- discovery stays
    # routed through Research Service, never worker -> Engine/MDS directly.
    for forbidden in ("127.0.0.1:8090", "127.0.0.1:8080", "strategy-engine:", "market-data-service:"):
        assert forbidden not in text


def test_reference_explains_component_id_vs_instance_id() -> None:
    text = REFERENCE_PATH.read_text(encoding="utf-8")
    assert "`component_id`" in text
    assert "`instance_id`" in text
    assert "mandatory" in text.lower()
    assert "unique" in text.lower()


def test_program_centrally_points_every_worker_to_the_reference() -> None:
    text = PROGRAM_PATH.read_text(encoding="utf-8")
    assert "autoresearch/references/strategy_specification_reference.md" in text
    assert "component-catalog" in text
    assert "do not discover strategy engine" in text.lower()


def test_planning_entry_point_still_points_to_program_md(tmp_path: Path) -> None:
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
    }
    prompt = render_planning_prompt(state, REPO_ROOT, tmp_path)
    assert str(PROGRAM_PATH) in prompt


def test_interpretation_entry_point_still_points_to_program_md(tmp_path: Path) -> None:
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 1,
        "contract_version": "bbb_autoresearch_state.v2",
    }
    prompt = render_interpretation_prompt(state, REPO_ROOT, tmp_path, "batch")
    assert str(PROGRAM_PATH) in prompt


def test_fresh_iteration_zero_bootstrap_also_points_to_program_md(tmp_path: Path) -> None:
    # iteration == 0 prepends bootstrap.md raw -- confirm the bootstrap-stage
    # worker (a distinct fresh-worker entry point) is not missing the pointer
    # chain either.
    state = {
        "session_id": "s1",
        "skill_path": ".claude/skills/ema-anchor-edge-research/SKILL.md",
        "iteration": 0,
        "contract_version": "bbb_autoresearch_state.v2",
    }
    prompt = render_planning_prompt(state, REPO_ROOT, tmp_path)
    assert "autoresearch/program.md" in prompt


def test_iteration_prompt_template_still_reads_program_path_first() -> None:
    # iteration.md is the legacy single-stage template; it is not wired to a
    # render_* function today, but it must not silently drop the same
    # program_path-first reading contract if it is ever reactivated.
    text = (REPO_ROOT / "autoresearch/prompts/iteration.md").read_text(encoding="utf-8")
    assert "{program_path}" in text
