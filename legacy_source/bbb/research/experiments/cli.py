"""Batch Experiment Management System — local operator/debug CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.experiments.batch_runner import BatchRunner
from research.experiments.models import BatchValidationError
from research.experiments.storage import write_batch_result
from research.experiments.validation import _repo_root, _relative_or_posix, load_and_validate_batch_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch Experiment Management System — local operator/debug CLI (not final UX)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate batch spec without running backtests")
    validate_parser.add_argument("--spec", type=Path, required=True, help="Path to batch spec JSON")

    run_parser = subparsers.add_parser("run-batch", help="Validate and run a batch experiment")
    run_parser.add_argument("--spec", type=Path, required=True, help="Path to batch spec JSON")

    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        validated = load_and_validate_batch_spec(args.spec)
    except BatchValidationError as exc:
        print(f"validation_error={exc}", file=sys.stderr)
        return 1

    print(f"experiment_id={validated.spec.experiment_id}")
    print(f"candidates_count={len(validated.candidates)}")
    print("status=ok")
    return 0


def cmd_run_batch(args: argparse.Namespace) -> int:
    root = _repo_root()
    try:
        validated = load_and_validate_batch_spec(args.spec, repo_root=root)
    except BatchValidationError as exc:
        print(f"validation_error={exc}", file=sys.stderr)
        return 1

    runner = BatchRunner(repo_root=root)
    result = runner.run(validated)
    output_path = write_batch_result(result)
    rel_output = _relative_or_posix(output_path, root)

    print(f"experiment_id={result.experiment_id}")
    print(f"candidates_count={result.candidates_count}")
    print(f"ok_count={result.ok_count}")
    print(f"failed_count={result.failed_count}")
    print(f"output_path={rel_output}")
    print(f"duration_sec={result.duration_sec:.3f}")
    print("status=ok" if result.failed_count == 0 else "status=partial")
    return 0 if result.ok_count > 0 or result.failed_count == 0 else 1


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        raise SystemExit(cmd_validate(args))
    if args.command == "run-batch":
        raise SystemExit(cmd_run_batch(args))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
