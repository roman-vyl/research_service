"""Synthetic tests for the `historical-managed-projection-cutover-v1` gate
harnesses (task 4.3): the comparison, horizon, call-count, corpus and
benchmark acceptance logic, plus the two CLIs' run functions wired to
in-process fakes. No live services."""

from __future__ import annotations

import dataclasses
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from managed_projection_benchmark import run_workload  # noqa: E402
from managed_projection_gate import (  # noqa: E402
    CountingStrategyEngine,
    EngineCallCounts,
    ParityReport,
    RunMeasurement,
    compare_runs,
    corpus_failures,
    evaluate_workload,
    event_horizons,
    parse_ps_cputime,
    projection_kind,
    within_horizon,
)
from managed_projection_parity import run_case  # noqa: E402

from research_service.application.backtests import (  # noqa: E402
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (  # noqa: E402
    ExplicitRange,
    HistoricalManagedProjectionDTO,
)
from research_service.execution.managed_policy_events import ManagedPolicyEvent  # noqa: E402
from test_batch_experiments import candidate, make_request  # noqa: E402
from test_single_instance_backtest import (  # noqa: E402
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_projection,
)


def _empty_managed() -> HistoricalManagedProjectionDTO:
    return HistoricalManagedProjectionDTO(conditions={}, distances={}, rules=())


def _outcome():
    projection = strategy_projection().model_copy(update={"managed": _empty_managed()})
    return RunSingleInstanceBacktest(
        FakeStrategyEngine(projection), FakeMarketData(market_frame())
    ).execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=True,
        )
    )


def _counts_for(outcome, *, replay: int | None = None, new: bool = False) -> EngineCallCounts:
    counts = EngineCallCounts(range=1)
    if not new:
        ids = [item.position.position_id for item in outcome.execution.positions]
        counts.managed_replay_trade_ids = ids
        counts.managed_replay = len(ids) if replay is None else replay
    elif replay is not None:
        counts.managed_replay = replay
    return counts


def _with_trade(outcome, **changes: Any):
    trade = outcome.accounting.trades[0].model_copy(update=changes)
    accounting = outcome.accounting.model_copy(update={"trades": (trade,)})
    return dataclasses.replace(outcome, accounting=accounting)


def _compare(old, new, old_counts=None, new_counts=None) -> ParityReport:
    return compare_runs(
        "case",
        old,
        new,
        old_counts or _counts_for(old),
        new_counts or _counts_for(new, new=True),
    )


# -- parity: trades, accounting, metrics ------------------------------------


def test_identical_runs_pass() -> None:
    outcome = _outcome()
    report = _compare(outcome, outcome)

    assert report.passed, report.failures
    assert report.trade_count == 1
    assert report.sides == {"long": 1, "short": 0}
    assert report.initialized_equals_opened
    assert report.kind == "atomic"


def test_semantic_trade_difference_fails_and_propagates_to_summary() -> None:
    outcome = _outcome()
    changed = _with_trade(outcome, net_pnl=outcome.accounting.trades[0].net_pnl + Decimal("1"))

    report = _compare(outcome, changed)

    assert not report.passed
    assert ("trade", "net_pnl") in {(item.scope, item.field) for item in report.failures}
    # candidate metrics are derived from trades, so they move too.
    assert any(item.scope == "metrics" for item in report.failures)


def test_accounting_summary_difference_fails() -> None:
    outcome = _outcome()
    accounting = outcome.accounting.model_copy(update={"final_equity": Decimal("1")})
    changed = dataclasses.replace(outcome, accounting=accounting)

    report = _compare(outcome, changed)

    assert ("accounting", "final_equity") in {(i.scope, i.field) for i in report.failures}


def test_label_fields_are_never_compared() -> None:
    outcome = _outcome()
    changed = _with_trade(outcome, trade_id="other", position_id="other", instance_id="other")

    assert _compare(outcome, changed).passed


@pytest.mark.parametrize(
    ("old_changes", "new_changes", "allowed"),
    [
        ({"exit_component_id": "break_even_stop"}, {"exit_component_id": None}, True),
        (
            {"exit_reason": "active_stop:break_even_stop"},
            {"exit_reason": "active_stop:managed_stop"},
            True,
        ),
        ({"exit_reason": "active_stop:x"}, {"exit_reason": "take_profit"}, False),
        (
            {"exit_reason": "runtime_exit:signal", "exit_kind": "signal"},
            {"exit_reason": "runtime_exit:market_close", "exit_kind": "market_close"},
            True,
        ),
        (
            {"exit_reason": "take_profit", "exit_kind": "take_profit"},
            {"exit_reason": "take_profit", "exit_kind": "stop_loss"},
            False,
        ),
        ({"exit_rule_id": "stop_a"}, {"exit_rule_id": "stop_b"}, False),
    ],
)
def test_allowed_diagnostic_differences(
    old_changes: dict[str, Any], new_changes: dict[str, Any], allowed: bool
) -> None:
    outcome = _outcome()
    report = _compare(_with_trade(outcome, **old_changes), _with_trade(outcome, **new_changes))

    assert report.passed is allowed
    if allowed:
        assert report.allowed


# -- parity: event horizon ----------------------------------------------------


def _event(position_id: str, bar_index: int, event_type: str = "phase_changed", **fields: Any):
    return ManagedPolicyEvent(
        position_id=position_id,
        side="long",
        time_ms=bar_index * 300_000,
        bar_index=bar_index,
        event_type=event_type,  # type: ignore[arg-type]
        rule_id=fields.pop("rule_id", "r"),
        **fields,
    )


def _run_stub(positions: list[tuple[str, int | None]], events: list[ManagedPolicyEvent], outcome):
    """An outcome whose positions/events are replaced; trades/accounting
    stay those of the real fake run, so only positions/events differ."""

    return SimpleNamespace(
        **{
            "strategy_evaluation": outcome.strategy_evaluation,
            "accounting": outcome.accounting,
            "execution": SimpleNamespace(
                positions=[
                    SimpleNamespace(
                        position=SimpleNamespace(position_id=position_id),
                        exit_fill=SimpleNamespace(bar_index=exit_bar) if exit_bar is not None else None,
                    )
                    for position_id, exit_bar in positions
                ]
            ),
            "managed_policy_events": tuple(events),
        }
    )


def _event_report(old_positions, old_events, new_positions, new_events) -> ParityReport:
    outcome = _outcome()
    old = _run_stub(old_positions, old_events, outcome)
    new = _run_stub(new_positions, new_events, outcome)
    old_counts = EngineCallCounts(
        range=1,
        managed_replay=len(old_positions),
        managed_replay_trade_ids=[position_id for position_id, _ in old_positions],
    )
    return compare_runs("case", old, new, old_counts, EngineCallCounts(range=1))


def test_closed_position_ignores_legacy_events_at_or_after_exit() -> None:
    report = _event_report(
        [("p1", 5)],
        [_event("p1", 2), _event("p1", 5), _event("p1", 9)],
        [("p1", 5)],
        [_event("p1", 2)],
    )

    assert report.passed, report.failures
    assert report.events_compared == 1


def test_closed_position_missing_event_within_horizon_fails() -> None:
    report = _event_report([("p1", 5)], [_event("p1", 2), _event("p1", 4)], [("p1", 5)], [_event("p1", 2)])

    assert [item.scope for item in report.failures] == ["events"]


def test_open_position_compares_through_the_last_bar() -> None:
    old_events = [_event("p1", 2), _event("p1", 40)]
    assert _event_report([("p1", None)], old_events, [("p1", None)], old_events).passed

    report = _event_report([("p1", None)], old_events, [("p1", None)], old_events[:1])
    assert not report.passed
    assert report.open_positions == 1


def test_new_event_beyond_its_own_horizon_fails() -> None:
    report = _event_report(
        [("p1", 5)], [_event("p1", 2)], [("p1", 5)], [_event("p1", 2), _event("p1", 6)]
    )

    assert "beyond_horizon" in {item.field for item in report.failures}


def test_event_fields_compared_and_diagnostic_metadata_ignored() -> None:
    old = [_event("p1", 2, price=Decimal("101"), metadata={"path_id": "htf", "children": {"a": True}})]
    same = [_event("p1", 2, price=Decimal("101.0"), metadata={"path_id": "htf"}, component_id=None)]
    other_path = [_event("p1", 2, price=Decimal("101"), metadata={"path_id": "fast"})]

    assert _event_report([("p1", 5)], old, [("p1", 5)], same).passed
    assert not _event_report([("p1", 5)], old, [("p1", 5)], other_path).passed


def test_positions_matched_by_order_not_id() -> None:
    report = _event_report(
        [("old-1", 5)], [_event("old-1", 2)], [("new-1", 5)], [_event("new-1", 2)]
    )

    assert report.passed, report.failures


def test_event_horizons_and_within_horizon_helpers() -> None:
    outcome = _outcome()
    horizons = event_horizons(outcome)
    assert horizons == [
        (
            outcome.execution.positions[0].position.position_id,
            outcome.execution.positions[0].exit_fill.bar_index,
        )
    ]
    events = [_event("a", 1), _event("a", 3), _event("b", 1)]
    assert [e.bar_index for e in within_horizon(events, "a", 3)] == [1]
    assert [e.bar_index for e in within_horizon(events, "a", None)] == [1, 3]


# -- parity: call counts and corpus ------------------------------------------


def test_new_replay_call_fails() -> None:
    outcome = _outcome()
    report = _compare(outcome, outcome, new_counts=_counts_for(outcome, new=True, replay=1))

    assert ("calls", "managed_replay") in {(i.scope, i.field) for i in report.failures}


def test_old_duplicate_replay_call_fails() -> None:
    outcome = _outcome()
    counts = _counts_for(outcome)
    counts.managed_replay_trade_ids = counts.managed_replay_trade_ids * 2
    counts.managed_replay = len(counts.managed_replay_trade_ids)

    report = _compare(outcome, outcome, old_counts=counts)

    assert "managed_replay_per_position" in {item.field for item in report.failures}


def test_uninitialized_position_is_reported_not_silently_passed() -> None:
    outcome = _outcome()
    counts = EngineCallCounts(range=1)  # OLD never initialized managed

    report = _compare(outcome, outcome, old_counts=counts)

    assert report.passed  # per-case comparison itself is fine...
    assert not report.initialized_equals_opened
    assert any("initialized" in problem for problem in corpus_failures([report]))  # ...the corpus is not


def _report(kind: str, long: int, short: int) -> ParityReport:
    report = ParityReport(case_id=f"{kind}-{long}-{short}", kind=kind)
    report.sides = {"long": long, "short": short}
    report.initialized_equals_opened = True
    return report


def test_corpus_requires_atomic_and_composite_with_both_sides() -> None:
    assert corpus_failures([_report("atomic", 3, 2), _report("composite", 1, 4)]) == []
    assert corpus_failures([_report("atomic", 3, 2)]) == ["no composite case"]
    assert corpus_failures([_report("atomic", 3, 0), _report("composite", 0, 1), _report("composite", 2, 0)]) == [
        "atomic cases have no short trades"
    ]


def test_projection_kind() -> None:
    assert projection_kind(strategy_projection()) == "unmanaged"
    managed = HistoricalManagedProjectionDTO.model_validate(
        {
            "conditions": {"a": {"long": [True] * 3, "short": [True] * 3}},
            "distances": {},
            "rules": [
                {
                    "kind": "phase_transition",
                    "rule_id": "r",
                    "target_phase": "proven",
                    "paths": [{"path_id": "p", "condition_id": "a"}],
                }
            ],
        }
    )
    assert projection_kind(strategy_projection().model_copy(update={"managed": managed})) == "composite"


# -- parity CLI run function, wired to fakes ---------------------------------


def test_run_case_runs_old_and_new_and_counts_calls() -> None:
    projection = strategy_projection().model_copy(update={"managed": _empty_managed()})
    case = {
        "case_id": "fake",
        "kind": "atomic",
        "request": SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=True,
        ).model_dump(mode="json"),
    }

    report, walls = run_case(case, FakeStrategyEngine(projection), FakeMarketData(market_frame()))

    assert report.passed, report.failures
    assert report.counts_old["managed_replay"] == 1
    assert report.counts_new["managed_replay"] == 0
    assert report.counts_old["range"] == report.counts_new["range"] == 1
    assert report.initialized_equals_opened
    assert set(walls) == {"old_wall_s", "new_wall_s"}


def test_run_case_rejects_a_mislabelled_case() -> None:
    projection = strategy_projection().model_copy(update={"managed": _empty_managed()})
    case = {
        "case_id": "fake",
        "kind": "composite",
        "request": SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
        ).model_dump(mode="json"),
    }

    with pytest.raises(ValueError, match="declared kind"):
        run_case(case, FakeStrategyEngine(projection), FakeMarketData(market_frame()))


# -- counting port ------------------------------------------------------------


def test_counting_port_counts_and_passes_through() -> None:
    inner = FakeStrategyEngine(strategy_projection())
    counting = CountingStrategyEngine(inner)

    request = make_request(candidate("a"), candidate("b"))
    assert counting.health() is True
    list(counting.evaluate_range_batch(_batch_request(request)))

    assert counting.counts.as_dict() == {
        "range": 0,
        "range_batch": 1,
        "range_batch_variants": 2,
        "managed_replay": 0,
    }


def _batch_request(request):
    from research_service.domain.contracts import (
        StrategyEvaluationBatchRequest,
        StrategyEvaluationBatchVariant,
    )

    return StrategyEvaluationBatchRequest(
        market=market_frame().market,
        variants=tuple(
            StrategyEvaluationBatchVariant(
                variant_id=item.candidate_id,
                instance_id=f"i-{item.candidate_id}",
                strategy_id=item.strategy.strategy_id,
                strategy_spec=item.strategy.raw_spec,
            )
            for item in request.candidates
        ),
    )


# -- benchmark ----------------------------------------------------------------


def _measurement(mode: str, wall: float, **overrides: Any) -> RunMeasurement:
    payload: dict[str, Any] = {
        "mode": mode,
        "wall_s": wall,
        "research_cpu_s": wall / 2,
        "engine_cpu_s": 1.0,
        "trade_count": 100,
        "candidate_count": 2,
        "counts": {
            "range": 0,
            "range_batch": 1,
            "range_batch_variants": 2,
            "managed_replay": 0 if mode == "new" else 100,
        },
    }
    payload.update(overrides)
    return RunMeasurement(**payload)


def _paired(new_walls: list[float], old_walls: list[float]) -> list[RunMeasurement]:
    return [_measurement("new", w) for w in new_walls] + [_measurement("old", w) for w in old_walls]


def test_benchmark_passes_on_median_improvement() -> None:
    summary, failures = evaluate_workload("w", _paired([1.0, 9.0, 1.2], [5.0, 4.0, 6.0]))

    assert failures == []
    assert summary["new"]["median_wall_s"] == 1.2
    assert summary["old"]["median_wall_s"] == 5.0
    assert summary["new"]["median_total_cpu_s"] == pytest.approx(1.6)


def test_benchmark_fails_when_median_is_not_lower() -> None:
    _summary, failures = evaluate_workload("w", _paired([5.0, 5.0, 5.0], [5.0, 4.0, 6.0]))

    assert failures == ["w: median NEW wall >= median OLD wall"]


def test_benchmark_requires_three_paired_runs_with_oracle() -> None:
    _summary, failures = evaluate_workload("w", _paired([1.0, 1.0], [5.0, 5.0]))

    assert failures == ["w: 2 paired runs < 3"]


def test_benchmark_without_oracle_gates_structure_only() -> None:
    summary, failures = evaluate_workload("w", [_measurement("new", 3.0)])

    assert failures == []
    assert summary["old"] is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"counts": {"range": 0, "range_batch": 1, "range_batch_variants": 2, "managed_replay": 3}},
            "w: NEW managed_replay=3",
        ),
        (
            {"counts": {"range": 0, "range_batch": 2, "range_batch_variants": 4, "managed_replay": 0}},
            "w: NEW Engine evaluations 4 != candidates 2",
        ),
        ({"failed_candidates": 1}, "w: new failed candidates=1"),
    ],
)
def test_benchmark_structural_failures(overrides: dict[str, Any], expected: str) -> None:
    _summary, failures = evaluate_workload("w", [_measurement("new", 1.0, **overrides)])

    assert expected in failures


def test_cpu_is_recorded_not_gated() -> None:
    runs = _paired([1.0, 1.0, 1.0], [5.0, 5.0, 5.0])
    for run in runs:
        if run.mode == "new":
            run.research_cpu_s = 50.0  # Research CPU far above OLD
    assert evaluate_workload("w", runs)[1] == []


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("00:01:23\n", 83.0),  # Linux mm:ss with hours
        ("1-02:03:04", 93_784.0),  # Linux dd-hh:mm:ss
        ("  0:01.52", 1.52),  # macOS mm:ss.ss
        ("1:02:03.50", 3_723.5),  # macOS hh:mm:ss.ss
    ],
)
def test_parse_ps_cputime(text: str, seconds: float) -> None:
    assert parse_ps_cputime(text) == pytest.approx(seconds)


def test_run_workload_with_fakes(tmp_path: Path) -> None:
    projection = strategy_projection().model_copy(update={"managed": _empty_managed()})
    request = make_request(
        candidate("a", managed_policy_enabled=True), candidate("b", managed_policy_enabled=True)
    )
    workload = {
        "workload_id": "fake",
        "kind": "atomic",
        "level": "low",
        "batch": request.model_dump(mode="json"),
    }

    summary, failures = run_workload(
        workload,
        FakeStrategyEngine(projection),
        FakeMarketData(market_frame()),
        artifacts_root=tmp_path,
        engine_pid=None,
        repeats=3,
        with_oracle=True,
    )

    new_runs = [run for run in summary["runs"] if run["mode"] == "new"]
    old_runs = [run for run in summary["runs"] if run["mode"] == "old"]
    assert len(new_runs) == len(old_runs) == 3
    assert all(run["counts"]["managed_replay"] == 0 for run in new_runs)
    assert all(run["counts"]["managed_replay"] == 2 for run in old_runs)
    assert all(run["counts"]["range_batch_variants"] == 2 for run in summary["runs"])
    assert all(run["engine_cpu_s"] is None for run in summary["runs"])
    assert summary["kind"] == "atomic" and summary["level"] == "low"
    # Wall on in-process fakes is noise; only the structural gates are
    # meaningful here.
    assert [f for f in failures if "median" not in f] == []
