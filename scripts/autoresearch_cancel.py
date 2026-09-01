#!/usr/bin/env python3
"""Request graceful cancellation of a local BBB AutoResearch session."""

from __future__ import annotations

import argparse
import sys

from autoresearch_supervisor import atomic_write_json, load_json, session_dir, utc_now, validate_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    args = parser.parse_args(argv)
    root = session_dir(args.session)
    state = load_json(root / "state.json")
    validate_state(state)
    if state["status"] in {"completed", "hard_stopped", "cancelled"}:
        print(f"session already terminal: {state['status']}")
        return 0
    marker = root / "cancel.requested.json"
    atomic_write_json(
        marker,
        {
            "contract_version": "bbb_autoresearch_cancellation.v1",
            "session_id": args.session,
            "requested_at": utc_now(),
        },
    )
    print(marker)
    return 0


if __name__ == "__main__":
    sys.exit(main())
