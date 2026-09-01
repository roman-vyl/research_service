from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.backtests import (
    PersistSingleInstanceRun,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_projection,
)


def completed_backtest():
    request = SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=900_000),
        execution=ExecutionPolicy(),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )
    outcome = RunSingleInstanceBacktest(
        FakeStrategyEngine(strategy_projection()),
        FakeMarketData(market_frame()),
    ).execute(request)
    return request, outcome


def _persist(store, request, outcome):
    return PersistSingleInstanceRun(store).execute(
        request,
        run_id=outcome.run_id,
        instance_id=outcome.instance_id,
        strategy_evaluation=outcome.strategy_evaluation,
        execution=outcome.execution,
        accounting=outcome.accounting,
        managed_policy_events=outcome.managed_policy_events,
    )


def test_persist_backtest_writes_versioned_atomic_bundle(tmp_path) -> None:
    request, outcome = completed_backtest()
    persisted = _persist(FilesystemArtifactStore(tmp_path), request, outcome)

    run_dir = tmp_path / outcome.run_id
    assert persisted.artifact_path == str(run_dir)
    assert run_dir.is_dir()
    assert {path.name for path in run_dir.iterdir()} == {
        "manifest.json",
        "request.json",
        "strategy_evaluation.json",
        "execution_events.json",
        "trades.json",
        "metrics.json",
        "managed_policy_events.json",
        "result.json",
    }

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == "research_run_artifacts.v1"
    assert manifest["run_id"] == outcome.run_id
    assert manifest["market_data_hash"] == "market-hash"
    assert len(manifest["files"]) == 7
    for record in manifest["files"]:
        payload = (run_dir / record["path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)

    # result.json references, not re-embeds, strategy_evaluation/trades/
    # execution_events -- I6.D shape (research-production-cutover-v1).
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert result["contract_version"] == "research_single_instance_run.v2"
    assert set(result["strategy_evaluation_ref"]) == {"path", "sha256"}
    assert result["strategy_evaluation_ref"]["path"] == "strategy_evaluation.json"
    assert "entry_opportunities" not in result

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["realised_trade_count"] == 1
    assert metrics["net_pnl"] == "47.90209790209790209790209790"

    # completed_backtest() uses managed_policy_enabled=False — the artifact
    # is still written, as an empty trace, not omitted.
    managed_events = json.loads(
        (run_dir / "managed_policy_events.json").read_text(encoding="utf-8")
    )
    assert managed_events["contract_version"] == "research_managed_policy_events.v1"
    assert managed_events["run_id"] == outcome.run_id
    assert managed_events["events"] == []


def test_existing_run_is_immutable(tmp_path) -> None:
    request, outcome = completed_backtest()
    store = FilesystemArtifactStore(tmp_path)
    _persist(store, request, outcome)

    with pytest.raises(FileExistsError, match="already exist"):
        _persist(store, request, outcome)


def test_failed_bundle_is_not_published(tmp_path) -> None:
    store = FilesystemArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe artifact path"):
        store.write_run_bundle("bad-run", {"../escape.json": b"{}"})

    assert not (tmp_path / "bad-run").exists()
    assert not list(tmp_path.glob(".bad-run.tmp-*"))


def test_request_result_identity_is_required(tmp_path) -> None:
    request, outcome = completed_backtest()
    with pytest.raises(ValueError, match="instance_id does not match"):
        PersistSingleInstanceRun(FilesystemArtifactStore(tmp_path)).execute(
            request,
            run_id=outcome.run_id,
            instance_id="ema_pullback:0000000000000000000000",
            strategy_evaluation=outcome.strategy_evaluation,
            execution=outcome.execution,
            accounting=outcome.accounting,
            managed_policy_events=outcome.managed_policy_events,
        )
