"""No-legs byte-identity gate (`research-frozen-partial-take-ladder-v1`
tasks 0.1-0.2).

Protects `research-run-artifacts-v1` "Byte-identical artifacts without
partial takes": a run without partial takes, on a continuous market,
persists the same bytes as before the ladder change. The hashes were
recorded on research_service main `7a07ca5` before any code change and
are never re-recorded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.application.backtests import (
    PersistSingleInstanceRun,
    RunSingleInstanceBacktest,
)
from no_legs_gate_fixture import (
    gate_market_frame,
    gate_projection,
    gate_request,
)
from test_single_instance_backtest import FakeMarketData, FakeStrategyEngine

REQUIREMENT = (
    'research-run-artifacts-v1 "Byte-identical artifacts without partial takes"'
)

RECORDED_SHA256 = {
    "strategy_evaluation.json": "99ac66ebb7bb0a627f200bf34ad11c7299fe16a8f3afb027e8b3076cc2a3289a",
    "trades.json": "0df1ef4d8fa2efa56220afa6d328b6fcd3a6f30df104d6da6a86d25d9eeac566",
    "execution_events.json": "c99ef7d908ab432b29b409c4081e3a002100d96317ee168533d661ab9d73edca",
    "metrics.json": "d6c6df530f5f8b620c32b534edc7036eda36ebf244152e5214464ddab41354ca",
    "result.json without run_id": "38b87ffdcf6275a53b2c8739d341a5ceb597358ac3e18b908cb4509ae770f8d8",
}

_LEVEL_EXITS = {"stop_loss", "managed_stop", "take_profit"}


def _run():
    request = gate_request()
    outcome = RunSingleInstanceBacktest(
        FakeStrategyEngine(gate_projection()),
        FakeMarketData(gate_market_frame()),
    ).execute(request)
    return request, outcome


def _persisted_hashes(tmp_path) -> dict[str, str]:
    request, outcome = _run()
    persisted = PersistSingleInstanceRun(FilesystemArtifactStore(tmp_path)).execute(
        request,
        run_id=outcome.run_id,
        instance_id=outcome.instance_id,
        strategy_evaluation=outcome.strategy_evaluation,
        execution=outcome.execution,
        accounting=outcome.accounting,
        managed_policy_events=outcome.managed_policy_events,
    )
    run_dir = Path(persisted.artifact_path)
    hashes = {
        name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        for name in (
            "strategy_evaluation.json",
            "trades.json",
            "execution_events.json",
            "metrics.json",
        )
    }
    result = json.loads((run_dir / "result.json").read_text())
    assert result.pop("run_id") == outcome.run_id
    hashes["result.json without run_id"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()
    return hashes


def test_gate_fixture_is_a_continuous_market_without_gap_through_bars() -> None:
    frame = gate_market_frame()
    for previous, candle in zip(frame.candles, frame.candles[1:]):
        assert candle.open == previous.close
    _request, outcome = _run()
    level_exits = [
        item.exit_fill
        for item in outcome.execution.positions
        if item.exit_fill is not None and item.exit_fill.candidate_type in _LEVEL_EXITS
    ]
    assert level_exits, REQUIREMENT
    for fill in level_exits:
        assert fill.fill_price == fill.reference_level, (REQUIREMENT, fill)


def test_gate_fixture_covers_every_closing_path_on_both_sides() -> None:
    _request, outcome = _run()
    observed = [
        (
            item.position.side,
            item.status,
            item.exit_fill.candidate_type if item.exit_fill is not None else None,
        )
        for item in outcome.execution.positions
    ]
    assert observed == [
        ("long", "closed", "stop_loss"),
        ("short", "closed", "take_profit"),
        ("long", "closed", "signal"),
        ("short", "closed", "runtime_close"),
        ("long", "closed", "managed_stop"),
        ("short", "open", None),
    ], REQUIREMENT


def test_no_legs_artifacts_are_byte_identical_to_the_recorded_baseline(tmp_path) -> None:
    assert _persisted_hashes(tmp_path) == RECORDED_SHA256, REQUIREMENT
