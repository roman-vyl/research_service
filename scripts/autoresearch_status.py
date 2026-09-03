#!/usr/bin/env python3
"""Print read-only status for a BBB AutoResearch session."""

from __future__ import annotations

import argparse
import json
import sys

from autoresearch_supervisor import load_json, session_dir, validate_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--journal-rows", type=int, default=5)
    args = parser.parse_args(argv)
    root = session_dir(args.session)
    state = load_json(root / "state.json")
    validate_state(state)
    rows = (root / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    output = {
        "session_id": state["session_id"],
        "status": state["status"],
        "phase": state["phase"],
        "iteration": state["iteration"],
        "last_iteration_result": state["last_iteration_result"],
        "next_experiment": state["next_experiment"],
        "stop_reason": state["stop_reason"],
        "budgets": state["budgets"],
        "recent_journal": [json.loads(line) for line in rows[-args.journal_rows :]],
    }
    if state["contract_version"] in {"bbb_autoresearch_state.v2", "bbb_autoresearch_state.v3"}:
        output.update(
            research_quality_policy=state["research_quality_policy"],
            active_stage_binding=state["active_stage_binding"],
            latest_quality_assessment=state["latest_quality_assessment"],
            promotion_history=state["promotion_history"],
        )
    if state["contract_version"] == "bbb_autoresearch_state.v3":
        starting = state["stage_contract"]["starting_strategy"]
        strategy = starting["strategy"]
        closed = {
            item["disposition"]["stage"]
            for item in state["stage_dispositions"]
            if item["disposition"]["status"] in {"characterized", "terminally_rejected"}
        }
        available = [state["active_stage"]]
        if {"B1_WIDTH", "B2_LOOKBACK"}.issubset(closed):
            available.append("B3_WIDTH_X_LOOKBACK")
        output.update(
            active_stage=state["active_stage"],
            frozen_control={
                "resolved_sha256": starting["resolved_sha256"],
                "strategy_id": strategy["strategy_id"],
                "ticker": strategy["ticker"],
                "base_timeframe": strategy["base_timeframe"],
            },
            phase_a_reference_recorded=bool(state["phase_a_references"]),
            phase_a_references=state["phase_a_references"],
            stage_dispositions=state["stage_dispositions"],
            available_stages=list(dict.fromkeys(available)),
        )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
