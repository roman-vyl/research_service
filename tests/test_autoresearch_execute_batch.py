from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from research_service.application.experiments import (
    BatchCandidateResult,
    BatchExperimentResult,
    PersistedBatchArtifacts,
)
from research_service.api.contracts.config import ValidationResult
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import autoresearch_execute_batch as adapter  # noqa: E402


def test_thin_adapter_validates_runs_and_persists_existing_contracts(
    tmp_path: Path, monkeypatch
) -> None:
    request = {
        "experiment_id": "exp-1",
        "strategy_id": "ema_pullback",
        "range_policy": "explicit_range",
        "range": {"from_ms": 0, "to_ms": 300000},
        "candidates": [
            {
                "candidate_id": "c1",
                "strategy": {
                    "enabled": True,
                    "strategy_id": "ema_pullback",
                    "ticker": "BTCUSDT.P",
                    "base_timeframe": "5m",
                    "raw_spec": {"anchor": {"period": 200}}
                },
                "managed_policy_enabled": False
            }
        ]
    }
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(request))
    calls: list[str] = []
    candidate = BatchCandidateResult(
        candidate_id="c1", run_id="run_1", instance_id="ema_pullback:abc", status="completed",
        artifact_path="/artifacts/run_1", realised_trade_count=0, open_position_count=0,
        final_equity="10000", gross_pnl="0", fees_paid="0", net_pnl="0",
        market_data_hash="hash", return_pct="0", max_drawdown="0",
        long={"trades": 0, "net_pnl": "0", "return_pct": "0"},
        short={"trades": 0, "net_pnl": "0", "return_pct": "0"},
    )
    result = BatchExperimentResult(
        experiment_id="exp-1", status="completed", candidate_count=1,
        completed_count=1, failed_count=0, candidates=(candidate,)
    )

    class Validate:
        def execute(self, draft):
            calls.append("validate")
            assert draft.instances[0].raw_spec == {"anchor": {"period": 200}}
            return ValidationResult(ok=True)

    class Run:
        def execute(self, parsed):
            calls.append("run")
            assert parsed.experiment_id == "exp-1"
            return result

    class Persist:
        def execute(self, parsed, actual):
            calls.append("persist")
            assert actual is result
            return PersistedBatchArtifacts(
                experiment_id="exp-1", artifact_path="/artifacts/batches/exp-1",
                summary_sha256="a" * 64
            )

    container = SimpleNamespace(close=lambda: calls.append("close"))
    services = SimpleNamespace(
        config_validation=Validate(), run_batch_experiment=Run(), persist_batch_experiment=Persist()
    )
    monkeypatch.setattr(
        adapter, "create_app", lambda settings: SimpleNamespace(
            state=SimpleNamespace(container=container, services=services)
        )
    )

    adapter.execute_batch(input_path, output_path)

    assert calls == ["validate", "run", "persist", "close"]
    output = json.loads(output_path.read_text())
    assert output["result"]["candidates"][0]["run_id"] == "run_1"
    assert output["persisted_batch"]["artifact_path"] == "/artifacts/batches/exp-1"
