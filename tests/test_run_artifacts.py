from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.backtests import (
    PersistSingleInstanceBacktest,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.execution import ExecutionPolicy
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_request,
    strategy_result,
)


def completed_backtest(run_id: str = "run-artifact-1"):
    request = SingleInstanceBacktestRequest(
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
    result = RunSingleInstanceBacktest(
        FakeStrategyEngine(strategy_result()),
        FakeMarketData(market_frame()),
    ).execute(request)
    return request, result


def test_persist_backtest_writes_versioned_atomic_bundle(tmp_path) -> None:
    request, result = completed_backtest()
    persisted = PersistSingleInstanceBacktest(FilesystemArtifactStore(tmp_path)).execute(
        request, result
    )

    run_dir = tmp_path / request.run_id
    assert persisted.artifact_path == str(run_dir)
    assert run_dir.is_dir()
    assert {path.name for path in run_dir.iterdir()} == {
        "manifest.json",
        "request.json",
        "strategy_evaluation.json",
        "execution_events.json",
        "trades.json",
        "metrics.json",
        "result.json",
    }

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == "research_run_artifacts.v1"
    assert manifest["run_id"] == request.run_id
    assert manifest["market_data_hash"] == "market-hash"
    assert len(manifest["files"]) == 6
    for record in manifest["files"]:
        payload = (run_dir / record["path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["realised_trade_count"] == 1
    assert metrics["net_pnl"] == "9.59000"


def test_existing_run_is_immutable(tmp_path) -> None:
    request, result = completed_backtest("immutable-run")
    use_case = PersistSingleInstanceBacktest(FilesystemArtifactStore(tmp_path))
    use_case.execute(request, result)

    with pytest.raises(FileExistsError, match="already exist"):
        use_case.execute(request, result)


def test_failed_bundle_is_not_published(tmp_path) -> None:
    store = FilesystemArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe artifact path"):
        store.write_run_bundle("bad-run", {"../escape.json": b"{}"})

    assert not (tmp_path / "bad-run").exists()
    assert not list(tmp_path.glob(".bad-run.tmp-*"))


def test_request_result_identity_is_required(tmp_path) -> None:
    request, result = completed_backtest("identity-a")
    mismatched = result.model_copy(update={"run_id": "identity-b"})

    with pytest.raises(ValueError, match="run_id differ"):
        PersistSingleInstanceBacktest(FilesystemArtifactStore(tmp_path)).execute(
            request,
            mismatched,
        )
