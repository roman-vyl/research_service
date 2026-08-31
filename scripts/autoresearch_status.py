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
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
