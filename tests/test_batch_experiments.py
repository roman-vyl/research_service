from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.application.backtests.artifacts import PersistedRunArtifacts
from research_service.application.experiments import (
    BatchCandidateRequest,
    BatchExperimentRequest,
    PersistBatchExperiment,
    RunBatchExperiment,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from test_managed_policy_events import ManagedEventsStrategyEngine
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_result,
)

# A batch has no pre-execution run_id anymore (run_id is Research-generated
# only after a candidate runs) — candidates are distinguished here by a test-
# only marker embedded in raw_spec instead, purely for these fakes to
# correlate calls; it plays no role in the real identity derivation logic
# other than (deliberately) making each candidate's instance_id distinct.


def make_backtest_request(marker: str) -> SingleInstanceBacktestRequest:
    identity = strategy_identity()
    return SingleInstanceBacktestRequest(
        strategy=identity.model_copy(
            update={"raw_spec": {**identity.raw_spec, "_test_marker": marker}}
        ),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )


def _marker(request: SingleInstanceBacktestRequest) -> str:
    return str(request.strategy.raw_spec["_test_marker"])


class FakeRunBacktest:
    def __init__(self, failing_markers: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing_markers = failing_markers or set()
        self.delegate = RunSingleInstanceBacktest(
            FakeStrategyEngine(strategy_result()),
            FakeMarketData(market_frame()),
        )

    def execute(self, request):
        marker = _marker(request)
        self.calls.append(marker)
        if marker in self.failing_markers:
            raise RuntimeError(f"boom:{marker}")
        return self.delegate.execute(request)


class FakePersistBacktest:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[str] = []
        self.managed_policy_events_calls: list[tuple] = []

    def execute(self, request, result, managed_policy_events=()):
        self.calls.append(result.run_id)
        self.managed_policy_events_calls.append(managed_policy_events)
        destination = self.root / result.run_id
        destination.mkdir(parents=True, exist_ok=False)
        return PersistedRunArtifacts(
            run_id=result.run_id,
            artifact_path=str(destination),
            manifest={
                "run_id": result.run_id,
                "instance_id": result.instance_id,
                "created_at_utc": "2026-07-14T00:00:00+00:00",
                "backtest_contract_version": result.contract_version,
                "strategy_contract_version": result.strategy_evaluation.contract_version,
                "execution_contract_version": result.execution.contract_version,
                "accounting_contract_version": result.accounting.contract_version,
                "market_data_hash": result.strategy_evaluation.market_data_hash,
                "files": [],
            },
        )


def make_request() -> BatchExperimentRequest:
    return BatchExperimentRequest(
        experiment_id="batch-1",
        description="sequential batch",
        candidates=(
            BatchCandidateRequest(
                candidate_id="a",
                backtest=make_backtest_request("a"),
                metadata={"rank": 1},
            ),
            BatchCandidateRequest(
                candidate_id="b",
                backtest=make_backtest_request("b"),
                metadata={"rank": 2},
            ),
            BatchCandidateRequest(
                candidate_id="c",
                backtest=make_backtest_request("c"),
                metadata={"rank": 3},
            ),
        ),
    )


def test_batch_runs_strictly_in_declared_order(tmp_path: Path) -> None:
    runner = FakeRunBacktest()
    persister = FakePersistBacktest(tmp_path)

    result = RunBatchExperiment(runner, persister).execute(make_request())

    assert runner.calls == ["a", "b", "c"]
    assert len(persister.calls) == 3
    assert result.status == "completed"
    assert result.completed_count == 3
    assert result.failed_count == 0
    assert [item.candidate_id for item in result.candidates] == ["a", "b", "c"]
    assert all(item.status == "completed" for item in result.candidates)
    assert all(item.run_id for item in result.candidates)


def test_candidate_failure_is_isolated_and_later_candidates_continue(tmp_path: Path) -> None:
    runner = FakeRunBacktest({"b"})
    persister = FakePersistBacktest(tmp_path)

    result = RunBatchExperiment(runner, persister).execute(make_request())

    assert runner.calls == ["a", "b", "c"]
    assert len(persister.calls) == 2
    assert result.status == "completed_with_failures"
    assert result.completed_count == 2
    assert result.failed_count == 1
    failed = result.candidates[1]
    assert failed.status == "failed"
    assert failed.error_type == "RuntimeError"
    assert failed.error_message == "boom:b"
    # No run was created for a failed candidate, so it has no generated
    # run_id (research-batch-experiments-v1, "Run identity generated only
    # on success") — but its instance_id is still derivable pre-execution.
    assert failed.run_id is None
    assert failed.instance_id
    assert result.candidates[2].status == "completed"
    assert result.candidates[2].run_id


def test_batch_summary_uses_new_backtest_accounting(tmp_path: Path) -> None:
    result = RunBatchExperiment(FakeRunBacktest(), FakePersistBacktest(tmp_path)).execute(
        make_request()
    )

    first = result.candidates[0]
    assert first.realised_trade_count == 1
    assert first.open_position_count == 0
    assert first.final_equity == Decimal("1009.59000")
    assert first.net_pnl == Decimal("9.59000")
    assert first.market_data_hash == "market-hash"
    assert first.metadata == {"rank": 1}


def test_batch_artifacts_are_published_atomically(tmp_path: Path) -> None:
    request = make_request()
    result = RunBatchExperiment(FakeRunBacktest(), FakePersistBacktest(tmp_path)).execute(request)
    persisted = PersistBatchExperiment(FilesystemArtifactStore(tmp_path)).execute(request, result)

    destination = tmp_path / "batches" / "batch-1"
    assert persisted.artifact_path == str(destination)
    assert (destination / "request.json").is_file()
    assert (destination / "summary.json").is_file()
    assert (destination / "manifest.json").is_file()
    assert len(persisted.summary_sha256) == 64


def test_batch_candidate_with_managed_policy_persists_real_events(tmp_path: Path) -> None:
    """Regression: the same managed backtest, run through the batch application
    path (not the standalone /backtests router), must persist the real
    managed-policy events captured by RunSingleInstanceBacktest's one
    authoritative outcome — not an empty artifact, which the caller-owned
    sink design silently produced for batch candidates."""

    run_backtest = RunSingleInstanceBacktest(
        ManagedEventsStrategyEngine(strategy_result()),
        FakeMarketData(market_frame()),
    )
    persist_backtest = PersistSingleInstanceBacktest(FilesystemArtifactStore(tmp_path))
    request = BatchExperimentRequest(
        experiment_id="batch-managed",
        candidates=(
            BatchCandidateRequest(
                candidate_id="managed-a",
                backtest=make_backtest_request("managed-a").model_copy(
                    update={"managed_policy_enabled": True}
                ),
            ),
        ),
    )

    result = RunBatchExperiment(run_backtest, persist_backtest).execute(request)

    assert result.status == "completed"
    assert result.candidates[0].status == "completed"
    run_id = result.candidates[0].run_id
    assert run_id

    events_path = tmp_path / run_id / "managed_policy_events.json"
    trace = json.loads(events_path.read_text(encoding="utf-8"))
    assert trace["run_id"] == run_id
    assert len(trace["events"]) == 2
    assert {event["event_type"] for event in trace["events"]} == {
        "phase_changed",
        "active_stop_updated",
    }


def test_batch_contract_rejects_duplicate_candidate_ids() -> None:
    candidate = BatchCandidateRequest(
        candidate_id="same",
        backtest=make_backtest_request("same"),
    )
    try:
        BatchExperimentRequest(experiment_id="bad", candidates=(candidate, candidate))
    except ValueError as exc:
        assert "candidate_id values must be unique" in str(exc)
    else:
        raise AssertionError("duplicate candidate ids were accepted")
