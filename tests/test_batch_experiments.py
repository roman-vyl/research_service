from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.backtests import (
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
from research_service.domain.execution import ExecutionPolicy
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_request,
    strategy_result,
)


def make_backtest_request(run_id: str) -> SingleInstanceBacktestRequest:
    return SingleInstanceBacktestRequest(
        run_id=run_id,
        strategy=strategy_request(),
        execution=ExecutionPolicy(quantity=Decimal("2")),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )


class FakeRunBacktest:
    def __init__(self, failing_run_ids: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing_run_ids = failing_run_ids or set()
        self.delegate = RunSingleInstanceBacktest(
            FakeStrategyEngine(strategy_result()),
            FakeMarketData(market_frame()),
        )

    def execute(self, request):
        self.calls.append(request.run_id)
        if request.run_id in self.failing_run_ids:
            raise RuntimeError(f"boom:{request.run_id}")
        return self.delegate.execute(request)


class FakePersistBacktest:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[str] = []

    def execute(self, request, result):
        self.calls.append(request.run_id)
        destination = self.root / request.run_id
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
                backtest=make_backtest_request("run-a"),
                metadata={"rank": 1},
            ),
            BatchCandidateRequest(
                candidate_id="b",
                backtest=make_backtest_request("run-b"),
                metadata={"rank": 2},
            ),
            BatchCandidateRequest(
                candidate_id="c",
                backtest=make_backtest_request("run-c"),
                metadata={"rank": 3},
            ),
        ),
    )


def test_batch_runs_strictly_in_declared_order(tmp_path: Path) -> None:
    runner = FakeRunBacktest()
    persister = FakePersistBacktest(tmp_path)

    result = RunBatchExperiment(runner, persister).execute(make_request())

    assert runner.calls == ["run-a", "run-b", "run-c"]
    assert persister.calls == ["run-a", "run-b", "run-c"]
    assert result.status == "completed"
    assert result.completed_count == 3
    assert result.failed_count == 0
    assert [item.candidate_id for item in result.candidates] == ["a", "b", "c"]
    assert all(item.status == "completed" for item in result.candidates)


def test_candidate_failure_is_isolated_and_later_candidates_continue(tmp_path: Path) -> None:
    runner = FakeRunBacktest({"run-b"})
    persister = FakePersistBacktest(tmp_path)

    result = RunBatchExperiment(runner, persister).execute(make_request())

    assert runner.calls == ["run-a", "run-b", "run-c"]
    assert persister.calls == ["run-a", "run-c"]
    assert result.status == "completed_with_failures"
    assert result.completed_count == 2
    assert result.failed_count == 1
    failed = result.candidates[1]
    assert failed.status == "failed"
    assert failed.error_type == "RuntimeError"
    assert failed.error_message == "boom:run-b"
    assert result.candidates[2].status == "completed"


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
