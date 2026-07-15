"""Standalone paired-run comparison: populate baseline_vs_managed_summary on managed report.

Usage (repo root):

    python -m research.experiments.compare_baseline_managed \\
        --baseline research/results/runs/<baseline_run>.json \\
        --managed research/results/runs/<managed_run>.json \\
        --output research/results/runs/<managed_run>.compared.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.strategies.ema_pullback.execution.managed_comparison import (
    apply_baseline_vs_managed_comparison_to_report,
)


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Populate baseline_vs_managed_summary on a managed run report.",
    )
    parser.add_argument("--baseline", required=True, help="Baseline run JSON artifact path")
    parser.add_argument("--managed", required=True, help="Managed run JSON artifact path")
    parser.add_argument(
        "--output",
        help="Output path (default: overwrite --managed in place)",
    )
    parser.add_argument("--baseline-variant", default=None, help="Baseline variant name")
    parser.add_argument("--managed-variant", default=None, help="Managed variant name")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline)
    managed_path = Path(args.managed)
    output_path = Path(args.output) if args.output else managed_path

    managed_report = _load_report(managed_path)
    baseline_report = _load_report(baseline_path)
    updated = apply_baseline_vs_managed_comparison_to_report(
        managed_report,
        baseline_report,
        managed_variant=args.managed_variant,
        baseline_variant=args.baseline_variant,
    )
    _write_report(output_path, updated)
    print(f"comparison_artifact={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
