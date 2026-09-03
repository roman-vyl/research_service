from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import autoresearch_status as status_module  # noqa: E402


def test_v3_status_reports_frozen_control_without_geometry_assumptions(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = tmp_path / "session"
    root.mkdir()
    (root / "journal.jsonl").write_text("", encoding="utf-8")
    state = {
        "contract_version": "bbb_autoresearch_state.v3",
        "session_id": "s1",
        "status": "initialized",
        "phase": "baseline",
        "iteration": 0,
        "last_iteration_result": None,
        "next_experiment": None,
        "stop_reason": None,
        "budgets": {},
        "research_quality_policy": {},
        "active_stage_binding": {},
        "latest_quality_assessment": None,
        "promotion_history": [],
        "active_stage": "A_CONTROL",
        "stage_contract": {
            "starting_strategy": {
                "resolved_sha256": "control-sha",
                "strategy": {
                    "strategy_id": "ema_pullback",
                    "ticker": "BTCUSDT.P",
                    "base_timeframe": "5m",
                },
            }
        },
        "phase_a_references": [],
        "stage_dispositions": [],
    }
    monkeypatch.setattr(status_module, "session_dir", lambda _session: root)
    monkeypatch.setattr(status_module, "load_json", lambda _path: state)
    monkeypatch.setattr(status_module, "validate_state", lambda _state: None)

    assert status_module.main(["--session", "s1"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["frozen_control"] == {
        "base_timeframe": "5m",
        "resolved_sha256": "control-sha",
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
    }
    assert output["phase_a_reference_recorded"] is False
    assert output["phase_a_references"] == []
    assert "configured_geometry_ids" not in output
    assert "completed_geometry_ids" not in output
