"""Shared logic for the `historical-managed-projection-cutover-v1` gates
(design D6/D7): a counting Strategy Engine port wrapper, the OLD-vs-NEW
parity comparison, and the benchmark acceptance evaluation.

Pure functions only -- no service URLs, no process spawning. The two
operator-run CLIs (`managed_projection_parity.py`,
`managed_projection_benchmark.py`) wire live services around these, and
`tests/test_managed_projection_gate.py` exercises them on synthetic
results.
"""

from __future__ import annotations

import re
import statistics
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from research_service.accounting.contracts import TradeAccountingResult
from research_service.application.backtests.materialize_backtest_projection import (
    SingleInstanceRunOutcome,
)
from research_service.application.experiments.candidate_summary import (
    derive_batch_candidate_summary,
)
from research_service.domain.contracts import (
    HistoricalExecutionProjectionDTO,
    ManagedReplayRequest,
    ManagedReplayResult,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationRequest,
)
from research_service.execution.managed_policy_events import ManagedPolicyEvent
from research_service.ports.strategy_engine import StrategyEnginePort

# -- counting port ------------------------------------------------------------


@dataclass
class EngineCallCounts:
    """Research-side Strategy Engine calls, per endpoint."""

    range: int = 0
    range_batch: int = 0
    range_batch_variants: int = 0
    managed_replay: int = 0
    managed_replay_trade_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        return {
            "range": self.range,
            "range_batch": self.range_batch,
            "range_batch_variants": self.range_batch_variants,
            "managed_replay": self.managed_replay,
        }


class CountingStrategyEngine:
    """Delegates every call to the wrapped port and counts the three
    evaluation endpoints this gate cares about. Everything else passes
    through untouched."""

    def __init__(self, inner: StrategyEnginePort) -> None:
        self._inner = inner
        self.counts = EngineCallCounts()

    def evaluate_range_projection(
        self, request: StrategyEvaluationRequest
    ) -> HistoricalExecutionProjectionDTO:
        self.counts.range += 1
        return self._inner.evaluate_range_projection(request)

    def evaluate_range_batch(
        self, request: StrategyEvaluationBatchRequest
    ) -> Iterator[StrategyEvaluationBatchVariantOutcome]:
        self.counts.range_batch += 1
        self.counts.range_batch_variants += len(request.variants)
        return self._inner.evaluate_range_batch(request)

    def evaluate_managed_replay(self, request: ManagedReplayRequest) -> ManagedReplayResult:
        self.counts.managed_replay += 1
        self.counts.managed_replay_trade_ids.append(request.trade_id)
        return self._inner.evaluate_managed_replay(request)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# -- parity -------------------------------------------------------------------

# Run-scoped labels: never compared (design D6).
LABEL_FIELDS = frozenset({"trade_id", "position_id", "instance_id"})
# Diagnostic-only fields the projection contract cannot carry (design D6).
ALLOWED_TRADE_FIELDS = frozenset({"exit_component_id"})
# Event fields compared (design D6); everything else is diagnostic.
EVENT_METADATA_KEYS = ("path_id", "take_profile")


@dataclass
class Difference:
    scope: str
    key: str
    field: str
    old: Any
    new: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "key": self.key,
            "field": self.field,
            "old": _jsonable(self.old),
            "new": _jsonable(self.new),
        }


@dataclass
class ParityReport:
    case_id: str
    kind: str
    trade_count: int = 0
    sides: dict[str, int] = field(default_factory=dict)
    open_positions: int = 0
    events_compared: int = 0
    counts_old: dict[str, int] = field(default_factory=dict)
    counts_new: dict[str, int] = field(default_factory=dict)
    managed_initialized_positions: int = 0
    initialized_equals_opened: bool = False
    failures: list[Difference] = field(default_factory=list)
    allowed: list[Difference] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "passed": self.passed,
            "trade_count": self.trade_count,
            "sides": self.sides,
            "open_positions": self.open_positions,
            "events_compared": self.events_compared,
            "counts_old": self.counts_old,
            "counts_new": self.counts_new,
            "managed_initialized_positions": self.managed_initialized_positions,
            "initialized_equals_opened": self.initialized_equals_opened,
            "failure_count": len(self.failures),
            "allowed_difference_count": len(self.allowed),
            "failures": [item.as_dict() for item in self.failures[:200]],
            "allowed": [item.as_dict() for item in self.allowed[:200]],
        }


def projection_kind(projection: HistoricalExecutionProjectionDTO) -> str:
    """`composite` when any managed phase rule carries `paths`, `atomic`
    for any other managed projection, `unmanaged` without one."""

    managed = projection.managed
    if managed is None:
        return "unmanaged"
    if any(rule.kind == "phase_transition" and rule.paths for rule in managed.rules):
        return "composite"
    return "atomic"


def compare_runs(
    case_id: str,
    old: SingleInstanceRunOutcome,
    new: SingleInstanceRunOutcome,
    old_counts: EngineCallCounts,
    new_counts: EngineCallCounts,
) -> ParityReport:
    """Full vertical OLD (legacy `/managed-replay` oracle) vs NEW
    (projection + local consumer) comparison for one case (design D6)."""

    report = ParityReport(case_id=case_id, kind=projection_kind(new.strategy_evaluation))
    report.counts_old = old_counts.as_dict()
    report.counts_new = new_counts.as_dict()

    _compare_trades(report, old.accounting, new.accounting)
    _compare_accounting(report, old.accounting, new.accounting)
    _compare_candidate_metrics(report, old.accounting, new.accounting)
    _compare_positions_and_events(report, old, new)
    _check_call_counts(report, old, old_counts, new_counts)
    return report


def _compare_trades(
    report: ParityReport, old: TradeAccountingResult, new: TradeAccountingResult
) -> None:
    report.trade_count = len(new.trades)
    report.sides = {
        side: sum(trade.side == side for trade in new.trades) for side in ("long", "short")
    }
    if len(old.trades) != len(new.trades):
        report.failures.append(
            Difference("trades", "*", "count", len(old.trades), len(new.trades))
        )
    for ordinal, (old_trade, new_trade) in enumerate(zip(old.trades, new.trades, strict=False)):
        key = f"trade#{ordinal + 1}"
        old_fields = old_trade.model_dump()
        new_fields = new_trade.model_dump()
        for name in sorted(set(old_fields) | set(new_fields)):
            if name in LABEL_FIELDS:
                continue
            old_value, new_value = old_fields.get(name), new_fields.get(name)
            if old_value == new_value:
                continue
            difference = Difference("trade", key, name, old_value, new_value)
            if _allowed_trade_difference(name, old_fields, new_fields):
                report.allowed.append(difference)
            else:
                report.failures.append(difference)


def _allowed_trade_difference(
    name: str, old_fields: dict[str, Any], new_fields: dict[str, Any]
) -> bool:
    if name in ALLOWED_TRADE_FIELDS:
        return True
    if name == "exit_reason":
        # Only the component suffix may differ (`active_stop:<component>`).
        return _reason_prefix(old_fields["exit_reason"]) == _reason_prefix(
            new_fields["exit_reason"]
        )
    if name == "exit_kind":
        # Only the literal on runtime exits: OLD carries the raw spec
        # string, NEW the canonical kind of the rule's exit_class.
        return _reason_prefix(new_fields["exit_reason"]) == "runtime_exit"
    return False


def _reason_prefix(reason: str) -> str:
    return reason.split(":", 1)[0]


def _compare_accounting(
    report: ParityReport, old: TradeAccountingResult, new: TradeAccountingResult
) -> None:
    old_fields = old.model_dump(exclude={"trades", "instance_id"})
    new_fields = new.model_dump(exclude={"trades", "instance_id"})
    for name in sorted(set(old_fields) | set(new_fields)):
        if old_fields.get(name) != new_fields.get(name):
            report.failures.append(
                Difference("accounting", "summary", name, old_fields.get(name), new_fields.get(name))
            )


def _compare_candidate_metrics(
    report: ParityReport, old: TradeAccountingResult, new: TradeAccountingResult
) -> None:
    old_fields = _flatten(_summary_fields(derive_batch_candidate_summary(old)))
    new_fields = _flatten(_summary_fields(derive_batch_candidate_summary(new)))
    for name in sorted(set(old_fields) | set(new_fields)):
        if old_fields.get(name) != new_fields.get(name):
            report.failures.append(
                Difference("metrics", "candidate", name, old_fields.get(name), new_fields.get(name))
            )


def event_horizons(outcome: SingleInstanceRunOutcome) -> list[tuple[str, int | None]]:
    """Per position, in execution order: (`position_id`, exclusive event
    horizon). A closed position's horizon is its exit bar index (events
    on bars `< exit_bar_index`); a position still open at the end of the
    range has `None` -- every event through the last bar (design D5/D6)."""

    horizons: list[tuple[str, int | None]] = []
    for item in outcome.execution.positions:
        exit_fill = item.exit_fill
        horizons.append(
            (item.position.position_id, exit_fill.bar_index if exit_fill is not None else None)
        )
    return horizons


def event_key(event: ManagedPolicyEvent) -> tuple[Any, ...]:
    return (
        event.bar_index,
        event.event_type,
        event.rule_id,
        event.from_phase,
        event.to_phase,
        event.price,
        *(event.metadata.get(key) for key in EVENT_METADATA_KEYS),
    )


def within_horizon(
    events: Sequence[ManagedPolicyEvent], position_id: str, horizon: int | None
) -> list[ManagedPolicyEvent]:
    return [
        event
        for event in events
        if event.position_id == position_id and (horizon is None or event.bar_index < horizon)
    ]


def _compare_positions_and_events(
    report: ParityReport, old: SingleInstanceRunOutcome, new: SingleInstanceRunOutcome
) -> None:
    old_horizons = event_horizons(old)
    new_horizons = event_horizons(new)
    report.open_positions = sum(horizon is None for _position, horizon in new_horizons)
    if len(old_horizons) != len(new_horizons):
        report.failures.append(
            Difference("positions", "*", "count", len(old_horizons), len(new_horizons))
        )
    for ordinal, ((old_id, old_horizon), (new_id, new_horizon)) in enumerate(
        zip(old_horizons, new_horizons, strict=False)
    ):
        key = f"position#{ordinal + 1}"
        if old_horizon != new_horizon:
            report.failures.append(
                Difference("positions", key, "exit_bar_index", old_horizon, new_horizon)
            )
            continue
        old_events = [event_key(e) for e in within_horizon(old.managed_policy_events, old_id, old_horizon)]
        # NEW never emits past its own horizon; filter anyway so a
        # violation shows up as a difference, not a silent pass.
        new_all = [e for e in new.managed_policy_events if e.position_id == new_id]
        new_events = [event_key(e) for e in within_horizon(new_all, new_id, new_horizon)]
        if len(new_events) != len(new_all):
            report.failures.append(
                Difference("events", key, "beyond_horizon", 0, len(new_all) - len(new_events))
            )
        report.events_compared += max(len(old_events), len(new_events))
        if old_events != new_events:
            first = next(
                (
                    index
                    for index, (a, b) in enumerate(zip(old_events, new_events, strict=False))
                    if a != b
                ),
                min(len(old_events), len(new_events)),
            )
            report.failures.append(
                Difference(
                    "events",
                    key,
                    f"sequence@{first} (old={len(old_events)}, new={len(new_events)})",
                    old_events[first] if first < len(old_events) else None,
                    new_events[first] if first < len(new_events) else None,
                )
            )


def _check_call_counts(
    report: ParityReport,
    old: SingleInstanceRunOutcome,
    old_counts: EngineCallCounts,
    new_counts: EngineCallCounts,
) -> None:
    if new_counts.managed_replay != 0:
        report.failures.append(
            Difference("calls", "new", "managed_replay", 0, new_counts.managed_replay)
        )
    initialized = old_counts.managed_replay_trade_ids
    unique = set(initialized)
    report.managed_initialized_positions = len(unique)
    if old_counts.managed_replay != len(unique):
        # One call per initialized position, never more.
        report.failures.append(
            Difference("calls", "old", "managed_replay_per_position", len(unique), old_counts.managed_replay)
        )
    opened = {item.position.position_id for item in old.execution.positions}
    if not unique <= opened:
        report.failures.append(
            Difference("calls", "old", "replay_for_unknown_position", sorted(opened), sorted(unique))
        )
    report.initialized_equals_opened = unique == opened


def corpus_failures(reports: Sequence[ParityReport]) -> list[str]:
    """Corpus requirement (design D6): at least one atomic and one
    composite case, each kind with long and short trades, and every
    opened position managed-initialized in the OLD run."""

    problems: list[str] = []
    for kind in ("atomic", "composite"):
        of_kind = [report for report in reports if report.kind == kind]
        if not of_kind:
            problems.append(f"no {kind} case")
            continue
        for side in ("long", "short"):
            if not any(report.sides.get(side) for report in of_kind):
                problems.append(f"{kind} cases have no {side} trades")
    for report in reports:
        if not report.initialized_equals_opened:
            problems.append(f"{report.case_id}: OLD managed-initialized positions != opened positions")
    return problems


# -- benchmark ----------------------------------------------------------------


@dataclass
class RunMeasurement:
    mode: str  # "old" | "new"
    wall_s: float
    research_cpu_s: float
    engine_cpu_s: float | None
    trade_count: int
    candidate_count: int
    counts: dict[str, int]
    failed_candidates: int = 0

    @property
    def total_cpu_s(self) -> float | None:
        if self.engine_cpu_s is None:
            return None
        return self.research_cpu_s + self.engine_cpu_s

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "wall_s": self.wall_s,
            "research_cpu_s": self.research_cpu_s,
            "engine_cpu_s": self.engine_cpu_s,
            "total_cpu_s": self.total_cpu_s,
            "trade_count": self.trade_count,
            "candidate_count": self.candidate_count,
            "failed_candidates": self.failed_candidates,
            "counts": self.counts,
        }


def evaluate_workload(
    workload_id: str, runs: Sequence[RunMeasurement], *, min_repeats: int = 3
) -> tuple[dict[str, Any], list[str]]:
    """Summary and hard-gate failures for one workload (design D7).

    Hard: every candidate completed in every run; NEW `/managed-replay` = 0; NEW Engine evaluations per
    candidate = 1 (one variant in `/range-batch` or one `/range` each,
    whatever the trade count); where OLD ran, >= `min_repeats` paired
    runs and median NEW wall < median OLD wall. CPU is recorded only."""

    failures: list[str] = []
    new_runs = [run for run in runs if run.mode == "new"]
    old_runs = [run for run in runs if run.mode == "old"]
    if not new_runs:
        failures.append(f"{workload_id}: no NEW run")
    for run in runs:
        if run.failed_candidates:
            # A fail-closed candidate is fast for the wrong reason.
            failures.append(f"{workload_id}: {run.mode} failed candidates={run.failed_candidates}")
    for run in new_runs:
        if run.counts.get("managed_replay", 0) != 0:
            failures.append(f"{workload_id}: NEW managed_replay={run.counts['managed_replay']}")
        evaluations = run.counts.get("range", 0) + run.counts.get("range_batch_variants", 0)
        if evaluations != run.candidate_count:
            failures.append(
                f"{workload_id}: NEW Engine evaluations {evaluations} != candidates {run.candidate_count}"
            )
    if old_runs:
        if len(old_runs) < min_repeats or len(new_runs) < min_repeats:
            failures.append(
                f"{workload_id}: {min(len(old_runs), len(new_runs))} paired runs < {min_repeats}"
            )
        elif statistics.median(r.wall_s for r in new_runs) >= statistics.median(
            r.wall_s for r in old_runs
        ):
            failures.append(f"{workload_id}: median NEW wall >= median OLD wall")

    summary = {
        "workload_id": workload_id,
        "trade_count": new_runs[0].trade_count if new_runs else None,
        "candidate_count": new_runs[0].candidate_count if new_runs else None,
        "new": _median_summary(new_runs),
        "old": _median_summary(old_runs) if old_runs else None,
        "runs": [run.as_dict() for run in runs],
    }
    return summary, failures


def _median_summary(runs: Sequence[RunMeasurement]) -> dict[str, Any] | None:
    if not runs:
        return None
    engine = [run.engine_cpu_s for run in runs if run.engine_cpu_s is not None]
    total = [run.total_cpu_s for run in runs if run.total_cpu_s is not None]
    return {
        "repeats": len(runs),
        "median_wall_s": statistics.median(run.wall_s for run in runs),
        "median_research_cpu_s": statistics.median(run.research_cpu_s for run in runs),
        "median_engine_cpu_s": statistics.median(engine) if engine else None,
        "median_total_cpu_s": statistics.median(total) if total else None,
        "counts": runs[0].counts,
    }


_CPUTIME = re.compile(r"^(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)$")


def parse_ps_cputime(text: str) -> float:
    """Seconds from `ps -o cputime=` output: Linux `[[dd-]hh:]mm:ss`,
    macOS `[hh:]mm:ss.ss`."""

    match = _CPUTIME.match(text.strip())
    if match is None:
        raise ValueError(f"unrecognized ps cputime: {text!r}")
    days, hours, minutes, seconds = match.groups()
    return (
        int(days or 0) * 86_400
        + int(hours or 0) * 3_600
        + int(minutes) * 60
        + float(seconds)
    )


def process_cpu_seconds(pid: int) -> float:
    """Cumulative CPU seconds of another process (portable Linux/macOS)."""

    output = subprocess.run(
        ["ps", "-o", "cputime=", "-p", str(pid)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return parse_ps_cputime(output)


# -- helpers ------------------------------------------------------------------


def _summary_fields(summary: Any) -> dict[str, Any]:
    """`BatchCandidateSummary` is a plain class; its sides are models."""

    return {
        name: value.model_dump() if hasattr(value, "model_dump") else value
        for name, value in vars(summary).items()
    }


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            out.update(_flatten(item, f"{prefix}{key}."))
        return out
    return {prefix.rstrip("."): value}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
