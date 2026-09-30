"""Managed projection performance gate (`historical-managed-projection-cutover-v1`
design D7, task 4.2). Operator-run against a live Strategy Engine and
Market Data Service; never run by CI.

Each workload is a real `BatchExperimentRequest` over a natural window
(low / medium / high trade count; trade counts are not constructed
artificially). It runs through the production `RunBatchExperiment` path:

  NEW: default -- one `/range-batch`, projection + local consumer;
  OLD (`--with-oracle`): the same batch with
       `allow_legacy_managed_replay_fallback=True` -- one
       `/managed-replay` per managed-initialized position.

Paired runs alternate OLD/NEW order per repeat. Recorded per run: trade
count, Research-side Engine calls (`/range`, `/range-batch` and its
variant count, `/managed-replay`), Research CPU (`time.process_time`),
Engine CPU (delta of `ps -o cputime` for `--engine-pid`, when given),
total CPU, wall. `ps` reports Engine CPU at coarse (Linux: whole-second)
resolution, so a small value or 0 on a short workload means "below
resolution", not zero work. Candidates persist into a throwaway artifact root
(same cost for OLD and NEW).

Hard gate: every candidate completes; NEW `/managed-replay` = 0; NEW
Engine evaluations = candidate count; with `--with-oracle`, >= 3 paired
runs and median NEW wall < median OLD wall. CPU is recorded, not gated
(Research CPU may legitimately grow: it now executes the lifecycle).

Workload file (JSON):

    {
      "workload_id": "atomic_high",
      "kind": "atomic",           # "atomic" or "composite", for the report
      "level": "high",            # "low" | "medium" | "high", for the report
      "batch": { ...BatchExperimentRequest... }
    }

Usage:

    python scripts/managed_projection_benchmark.py \\
        --workload w/atomic_low.json --workload w/atomic_high.json \\
        --workload w/composite_low.json --workload w/composite_high.json \\
        --strategy-engine-url http://127.0.0.1:8081 \\
        --market-data-url http://127.0.0.1:8082 \\
        --engine-pid 12345 --with-oracle --repeats 3 \\
        --report benchmark-report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from managed_projection_gate import (  # noqa: E402
    CountingStrategyEngine,
    RunMeasurement,
    evaluate_workload,
    process_cpu_seconds,
)

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore  # noqa: E402
from research_service.adapters.http.market_data_client import HttpMarketDataClient  # noqa: E402
from research_service.adapters.http.strategy_engine_client import (  # noqa: E402
    HttpStrategyEngineClient,
)
from research_service.application.backtests.materialize_backtest_projection import (  # noqa: E402
    MaterializeBacktestProjectionOutcome,
)
from research_service.application.backtests.persist_run import PersistSingleInstanceRun  # noqa: E402
from research_service.application.experiments.contracts import BatchExperimentRequest  # noqa: E402
from research_service.application.experiments.run_batch import RunBatchExperiment  # noqa: E402
from research_service.ports.market_data import MarketDataPort  # noqa: E402
from research_service.ports.strategy_engine import StrategyEnginePort  # noqa: E402


def measure_batch(
    mode: str,
    request: BatchExperimentRequest,
    strategy_engine: StrategyEnginePort,
    market_data: MarketDataPort,
    artifacts_root: Path,
    engine_pid: int | None,
) -> RunMeasurement:
    """One timed batch run. `mode` "old" forces the legacy oracle path."""

    counting = CountingStrategyEngine(strategy_engine)
    store = FilesystemArtifactStore(artifacts_root / f"{mode}-{time.time_ns()}")
    store.ensure_ready()
    use_case = RunBatchExperiment(
        counting,
        market_data,
        MaterializeBacktestProjectionOutcome(
            counting, allow_legacy_managed_replay_fallback=(mode == "old")
        ),
        PersistSingleInstanceRun(store),
    )

    engine_before = process_cpu_seconds(engine_pid) if engine_pid is not None else None
    cpu_before = time.process_time()
    wall_before = time.perf_counter()
    result = use_case.execute(request)
    wall = time.perf_counter() - wall_before
    research_cpu = time.process_time() - cpu_before
    engine_cpu = (
        process_cpu_seconds(engine_pid) - engine_before
        if engine_pid is not None and engine_before is not None
        else None
    )

    return RunMeasurement(
        mode=mode,
        wall_s=wall,
        research_cpu_s=research_cpu,
        engine_cpu_s=engine_cpu,
        trade_count=sum(item.realised_trade_count or 0 for item in result.candidates),
        candidate_count=result.candidate_count,
        counts=counting.counts.as_dict(),
        failed_candidates=result.failed_count,
    )


def run_workload(
    workload: dict[str, Any],
    strategy_engine: StrategyEnginePort,
    market_data: MarketDataPort,
    *,
    artifacts_root: Path,
    engine_pid: int | None,
    repeats: int,
    with_oracle: bool,
) -> tuple[dict[str, Any], list[str]]:
    request = BatchExperimentRequest.model_validate(workload["batch"])
    runs: list[RunMeasurement] = []
    for repeat in range(repeats):
        # Alternate the order of each pair so neither side always runs
        # against a warm or a cold Engine/MDS.
        modes = ["new", "old"] if repeat % 2 == 0 else ["old", "new"]
        for mode in modes:
            if mode == "old" and not with_oracle:
                continue
            run = measure_batch(mode, request, strategy_engine, market_data, artifacts_root, engine_pid)
            runs.append(run)
            print(
                f"{workload['workload_id']} #{repeat + 1} {mode}: wall={run.wall_s:.2f}s "
                f"research_cpu={run.research_cpu_s:.2f}s engine_cpu={run.engine_cpu_s} "
                f"trades={run.trade_count} counts={run.counts} failed={run.failed_candidates}"
            )
    summary, failures = evaluate_workload(workload["workload_id"], runs)
    summary["kind"] = workload.get("kind")
    summary["level"] = workload.get("level")
    return summary, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workload", action="append", required=True, type=Path)
    parser.add_argument("--strategy-engine-url", required=True)
    parser.add_argument("--market-data-url", required=True)
    parser.add_argument("--engine-pid", type=int, default=None)
    parser.add_argument("--with-oracle", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--artifacts-root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--report", type=Path, default=Path("managed-projection-benchmark-report.json"))
    args = parser.parse_args(argv)
    if args.with_oracle and args.repeats < 3:
        parser.error("--with-oracle requires --repeats >= 3 (design D7)")

    strategy_engine = HttpStrategyEngineClient(args.strategy_engine_url, args.timeout_seconds)
    market_data = HttpMarketDataClient(args.market_data_url)
    summaries: list[dict[str, Any]] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="managed-benchmark-") as scratch:
        artifacts_root = args.artifacts_root or Path(scratch)
        try:
            for path in args.workload:
                summary, workload_failures = run_workload(
                    json.loads(path.read_text()),
                    strategy_engine,
                    market_data,
                    artifacts_root=artifacts_root,
                    engine_pid=args.engine_pid,
                    repeats=args.repeats,
                    with_oracle=args.with_oracle,
                )
                summaries.append(summary)
                failures.extend(workload_failures)
        finally:
            strategy_engine.close()
            market_data.close()

    for failure in failures:
        print(f"gate: {failure}")
    passed = not failures
    args.report.write_text(
        json.dumps(
            {
                "gate": "historical-managed-projection-cutover-v1/benchmark",
                "passed": passed,
                "failures": failures,
                "engine_cpu_measured": args.engine_pid is not None,
                "workloads": summaries,
            },
            indent=2,
            default=str,
        )
    )
    print(f"report: {args.report} -> {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
