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
from research_service.application.backtests.read_artifacts import ReadResearchRuns
from research_service.domain.contracts import (
    ExitAttributionDTO,
    ExplicitRange,
    PartialTakeLegDTO,
)
from research_service.domain.execution import ExecutionPolicy
from no_legs_gate_fixture import (
    gate_market_frame,
    gate_opportunities,
    gate_projection,
    gate_request,
)
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


# --- partial take content (research-frozen-partial-take-ladder-v1 7.1) -----

def _gate_run(opportunities=None):
    request = gate_request()
    outcome = RunSingleInstanceBacktest(
        FakeStrategyEngine(gate_projection(opportunities)),
        FakeMarketData(gate_market_frame()),
    ).execute(request)
    return request, outcome


def _laddered_opportunities():
    # The short entry at bar 3 (anchor 97, final take 94.09) gets one leg at
    # 1% (96.03), touched on bar 4 before the final take on bar 5.
    opportunities = list(gate_opportunities())
    opportunities[1] = opportunities[1].model_copy(
        update={
            "partial_takes": (
                PartialTakeLegDTO(
                    take_id="pt_1pct",
                    ratio=0.01,
                    fraction_of_initial=0.25,
                    attribution=ExitAttributionDTO(
                        rule_id="pt_1pct", component_id="pct_partial_take", exit_kind="partial_take"
                    ),
                ),
            )
        }
    )
    return tuple(opportunities)


def test_ladder_content_round_trips_through_persisted_artifacts(tmp_path) -> None:
    request, outcome = _gate_run(_laddered_opportunities())
    store = FilesystemArtifactStore(tmp_path)
    _persist(store, request, outcome)
    run_dir = tmp_path / outcome.run_id

    evaluation = json.loads((run_dir / "strategy_evaluation.json").read_text())
    legs = [o.get("partial_takes") for o in evaluation["entry_opportunities"]]
    assert legs[1] == [
        {
            "take_id": "pt_1pct",
            "ratio": 0.01,
            "fraction_of_initial": 0.25,
            "attribution": {
                "rule_id": "pt_1pct",
                "component_id": "pct_partial_take",
                "exit_kind": "partial_take",
            },
        }
    ]
    assert [leg for i, leg in enumerate(legs) if i != 1] == [None] * 5

    events = json.loads((run_dir / "execution_events.json").read_text())
    reduced = [event for event in events if event["event_type"] == "position_reduced"]
    assert len(reduced) == 1 and reduced[0]["bar_index"] == 4

    trades = json.loads((run_dir / "trades.json").read_text())
    laddered = [trade for trade in trades if "exit_fills" in trade]
    assert len(laddered) == 1
    assert [fill["kind"] for fill in laddered[0]["exit_fills"]] == ["partial_take", "final"]
    assert all("exit_fills" not in t and "average_exit_price" not in t for t in trades if t is not laddered[0])

    detail = ReadResearchRuns(store).detail(outcome.run_id)
    assert detail.result.trades == outcome.accounting.trades
    assert detail.result.execution_events == outcome.execution.events
    assert detail.result.strategy_evaluation == outcome.strategy_evaluation


def test_artifacts_written_before_the_ladder_still_read(tmp_path) -> None:
    # The no-legs gate proves these bytes equal the pre-ladder bytes
    # (recorded on main 7a07ca5), so reading them is reading an old run.
    request, outcome = _gate_run()
    store = FilesystemArtifactStore(tmp_path)
    _persist(store, request, outcome)
    detail = ReadResearchRuns(store).detail(outcome.run_id)
    assert detail.result.trades and all(
        trade.exit_fills == () and trade.average_exit_price is None
        for trade in detail.result.trades
    )
    assert all(o.partial_takes == () for o in detail.result.strategy_evaluation.entry_opportunities)
