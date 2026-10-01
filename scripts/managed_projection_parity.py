"""OLD-vs-NEW managed parity gate (`historical-managed-projection-cutover-v1`
design D6, task 4.1). Operator-run against a live Strategy Engine and
Market Data Service; never run by CI.

For every case file it runs the same `SingleInstanceBacktestRequest`
twice through the real `RunSingleInstanceBacktest` seam:

  OLD: `allow_legacy_managed_replay_fallback=True` -- one
       `/managed-replay` call per managed-initialized position;
  NEW: default -- one `HistoricalManagedProjection` + the local
       incremental consumer, zero `/managed-replay` calls.

and compares every `TradeRecord` field (minus run-scoped labels), the
accounting summary, the batch candidate metrics, positions, and managed
events over the D5 horizon (closed: `bar_index < exit_bar_index`; open
at end: through the last bar). Allowed diagnostic differences are
reported separately. See `managed_projection_gate.py`.

Case file (JSON):

    {
      "case_id": "ema500_rsi87_atomic",
      "kind": "atomic",            # or "composite"; verified against the projection
      "request": { ...SingleInstanceBacktestRequest... }
    }

Usage:

    python scripts/managed_projection_parity.py \\
        --case cases/atomic.json --case cases/composite.json \\
        --strategy-engine-url http://127.0.0.1:8081 \\
        --market-data-url http://127.0.0.1:8082 \\
        --report parity-report.json

Exit code 0 only when every case passes and the corpus requirement
(atomic + composite, long + short each, all opened positions managed-
initialized in OLD) holds; `--allow-incomplete-corpus` downgrades the
corpus requirement to a warning (for ad-hoc single-case checks).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from managed_projection_gate import (  # noqa: E402
    CountingStrategyEngine,
    ParityReport,
    compare_runs,
    corpus_failures,
    projection_kind,
)

from research_service.adapters.http.market_data_client import HttpMarketDataClient  # noqa: E402
from research_service.adapters.http.strategy_engine_client import (  # noqa: E402
    HttpStrategyEngineClient,
)
from research_service.application.backtests import (  # noqa: E402
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.ports.market_data import MarketDataPort  # noqa: E402
from research_service.ports.strategy_engine import StrategyEnginePort  # noqa: E402


def run_case(
    case: dict[str, Any],
    strategy_engine: StrategyEnginePort,
    market_data: MarketDataPort,
) -> tuple[ParityReport, dict[str, float]]:
    request = SingleInstanceBacktestRequest.model_validate(case["request"])
    if not request.managed_policy_enabled:
        raise ValueError(f"{case['case_id']}: parity requires managed_policy_enabled=true")

    old_engine = CountingStrategyEngine(strategy_engine)
    started = time.perf_counter()
    old = RunSingleInstanceBacktest(
        old_engine, market_data, allow_legacy_managed_replay_fallback=True
    ).execute(request)
    old_wall = time.perf_counter() - started

    new_engine = CountingStrategyEngine(strategy_engine)
    started = time.perf_counter()
    new = RunSingleInstanceBacktest(new_engine, market_data).execute(request)
    new_wall = time.perf_counter() - started

    report = compare_runs(case["case_id"], old, new, old_engine.counts, new_engine.counts)
    declared = case.get("kind")
    actual = projection_kind(new.strategy_evaluation)
    if declared is not None and declared != actual:
        raise ValueError(f"{case['case_id']}: declared kind {declared!r}, projection is {actual!r}")
    return report, {"old_wall_s": old_wall, "new_wall_s": new_wall}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", action="append", required=True, type=Path)
    parser.add_argument("--strategy-engine-url", required=True)
    parser.add_argument("--market-data-url", required=True)
    parser.add_argument("--report", type=Path, default=Path("managed-projection-parity-report.json"))
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--allow-incomplete-corpus", action="store_true")
    args = parser.parse_args(argv)

    strategy_engine = HttpStrategyEngineClient(args.strategy_engine_url, args.timeout_seconds)
    market_data = HttpMarketDataClient(args.market_data_url)
    reports: list[ParityReport] = []
    walls: dict[str, dict[str, float]] = {}
    try:
        for path in args.case:
            case = json.loads(path.read_text())
            report, wall = run_case(case, strategy_engine, market_data)
            reports.append(report)
            walls[report.case_id] = wall
            print(
                f"{report.case_id} [{report.kind}]: {'PASS' if report.passed else 'FAIL'} "
                f"trades={report.trade_count} sides={report.sides} open={report.open_positions} "
                f"events={report.events_compared} failures={len(report.failures)} "
                f"allowed={len(report.allowed)} replay old/new="
                f"{report.counts_old['managed_replay']}/{report.counts_new['managed_replay']}"
            )
    finally:
        strategy_engine.close()
        market_data.close()

    corpus = corpus_failures(reports)
    for problem in corpus:
        print(f"corpus: {problem}")
    passed = all(report.passed for report in reports) and (
        not corpus or args.allow_incomplete_corpus
    )
    args.report.write_text(
        json.dumps(
            {
                "gate": "historical-managed-projection-cutover-v1/parity",
                "passed": passed,
                "corpus_failures": corpus,
                "cases": [report.as_dict() | {"wall": walls[report.case_id]} for report in reports],
            },
            indent=2,
        )
    )
    print(f"report: {args.report} -> {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
