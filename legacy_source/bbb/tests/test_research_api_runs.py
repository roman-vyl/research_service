"""Research API BFF — runs endpoints.

Requires: ``pip install -e ".[dev,workbench-api]"`` (fastapi, httpx).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from research_api.main import app
from research_api.services.results_reader import (
    UnsupportedSchemaVersionError,
    list_run_summaries,
    load_run_report,
    parse_run_report,
)
from research_api.services.run_id import InvalidRunIdError, validate_run_id

_SAMPLE_REPORT = {
    "run_id": "2026-05-01T120000Z_ema_pullback_BTCUSDT_5m",
    "created_at": "2026-05-01T12:00:00Z",
    "report_schema_version": 3,
    "family": "ema_pullback",
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "candles": 10,
    "data_range": {"from_open_time_ms": 1, "to_open_time_ms": 2},
    "variants_count": 1,
    "variants": [
        {
            "variant": "v1",
            "config_id": "cfg",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "strategy_spec": {"variant": "v1"},
            "metrics": {
                "long": {
                    "trades": 0,
                    "pnl": 0.0,
                    "return_pct": 0.0,
                    "profit_factor": None,
                    "win_rate": None,
                },
                "short": {
                    "trades": 0,
                    "pnl": 0.0,
                    "return_pct": 0.0,
                    "profit_factor": None,
                    "win_rate": None,
                },
                "total": {
                    "trades": 1,
                    "pnl": 10.0,
                    "return_pct": 0.01,
                    "profit_factor": None,
                    "win_rate": None,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                },
                "open_trades": {"long": 0, "short": 0, "total": 0},
            },
            "component_counters": [],
            "trade_records": [
                {
                    "trade_id": 1,
                    "direction": "long",
                    "status": "closed",
                    "entry_time_ms": 1000,
                    "exit_time_ms": 2000,
                    "entry_price": 1.0,
                    "exit_price": 1.1,
                    "size": 0.1,
                    "pnl": 1.0,
                    "return_pct": 0.01,
                    "exit_reason": "stop_loss:sl1",
                }
            ],
        }
    ],
}

_DIAGNOSTIC_BUCKET = {
    "trades": 1,
    "pnl": 9.0,
    "gross_pnl": 10.0,
    "fees_paid": 1.0,
    "profit_factor": None,
    "win_rate": 1.0,
    "avg_return_pct": 0.09,
    "avg_hold_bars": 3.0,
}

_EMPTY_PROFILE_BUCKET = {
    "trades": 0,
    "pnl": 0.0,
    "gross_pnl": 0.0,
    "fees_paid": 0.0,
    "profit_factor": None,
    "win_rate": None,
    "avg_return_pct": None,
    "avg_hold_bars": None,
    "exit_reason_mix": {},
}

_PROFILE_SIDE_SECTION = {
    "aligned": {**_DIAGNOSTIC_BUCKET, "exit_reason_mix": {"signal:rsi_exit": 1}},
    "countertrend": _EMPTY_PROFILE_BUCKET,
    "neutral": _EMPTY_PROFILE_BUCKET,
    "total": {**_DIAGNOSTIC_BUCKET, "exit_reason_mix": {"signal:rsi_exit": 1}},
}

_SAMPLE_REPORT_V4 = {
    **_SAMPLE_REPORT,
    "report_schema_version": 4,
    "variants": [
        {
            **_SAMPLE_REPORT["variants"][0],
            "metrics": {
                **_SAMPLE_REPORT["variants"][0]["metrics"],
                "profile_breakdown": {
                    "aligned": {
                        **_DIAGNOSTIC_BUCKET,
                        "exit_reason_mix": {"signal:rsi_exit": 1},
                    },
                    "countertrend": {
                        "trades": 0,
                        "pnl": 0.0,
                        "gross_pnl": 0.0,
                        "fees_paid": 0.0,
                        "profit_factor": None,
                        "win_rate": None,
                        "avg_return_pct": None,
                        "avg_hold_bars": None,
                        "exit_reason_mix": {},
                    },
                    "neutral": {
                        "trades": 0,
                        "pnl": 0.0,
                        "gross_pnl": 0.0,
                        "fees_paid": 0.0,
                        "profit_factor": None,
                        "win_rate": None,
                        "avg_return_pct": None,
                        "avg_hold_bars": None,
                        "exit_reason_mix": {},
                    },
                },
                "exit_reason_breakdown": {
                    "signal:rsi_exit": _DIAGNOSTIC_BUCKET,
                },
                "fee_diagnostics": {
                    "total_fees_paid": 1.0,
                    "gross_pnl": 10.0,
                    "net_pnl": 9.0,
                    "fees_rate": 0.0006,
                    "fees_as_pct_of_gross_profit": 0.1,
                },
            },
            "trade_records": [
                {
                    **_SAMPLE_REPORT["variants"][0]["trade_records"][0],
                    "entry_profile": "aligned",
                    "entry_context_state": "up",
                    "active_exit_profile": "aligned",
                    "exit_group": "profile",
                    "exit_profile": "aligned",
                    "exit_component_id": "rsi_signal_exit",
                    "exit_instance_id": "rsi_exit",
                    "exit_kind": "signal",
                    "gross_pnl": 10.0,
                    "fees_paid": 1.0,
                    "gross_return_pct": 0.1,
                    "hold_bars": 3,
                    "hold_minutes": 15,
                }
            ],
        }
    ],
}

_QUALITY_BUCKET = {
    "trades": 1,
    "avg_mfe_atr": None,
    "avg_mfe_pct": 0.04,
    "avg_capture_ratio": 0.25,
    "avg_giveback_atr": None,
    "avg_giveback_pct": 0.03,
    "exit_reason_mix": {"signal:ema_cross": 1},
}

_EXIT_COMPONENT_QUALITY_BUCKET = {
    "trades": 1,
    "avg_mfe_atr": None,
    "avg_mfe_pct": 0.04,
    "avg_capture_ratio": 0.25,
    "avg_giveback_atr": None,
    "avg_giveback_pct": 0.03,
    "quality_flag_mix": {"high_mfe_low_capture": 1, "signal_exit_giveback_failure": 1},
    "signal_exit_winners": 0,
    "signal_exit_giveback_failures": 1,
}

_TRADE_QUALITY_CONFIG = {
    "schema": "trade-exit-quality-diagnostics-v1",
    "high_mfe_atr": 2.0,
    "high_mfe_pct_fallback": 0.02,
    "high_capture_ratio": 0.60,
    "low_capture_ratio": 0.30,
    "low_mfe_atr": 1.0,
    "low_mfe_pct_fallback": 0.005,
    "giveback_failure_atr": 1.5,
    "atr_source": None,
}

_SAMPLE_REPORT_V5 = {
    **_SAMPLE_REPORT_V4,
    "report_schema_version": 5,
    "trade_quality_config": _TRADE_QUALITY_CONFIG,
    "variants": [
        {
            **_SAMPLE_REPORT_V4["variants"][0],
            "metrics": {
                **_SAMPLE_REPORT_V4["variants"][0]["metrics"],
                "profile_side_breakdown": {
                    "long": _PROFILE_SIDE_SECTION,
                    "short": {
                        "aligned": _EMPTY_PROFILE_BUCKET,
                        "countertrend": _EMPTY_PROFILE_BUCKET,
                        "neutral": _EMPTY_PROFILE_BUCKET,
                        "total": _EMPTY_PROFILE_BUCKET,
                    },
                    "total": _PROFILE_SIDE_SECTION,
                },
                "quality_flag_breakdown": {
                    "high_mfe_low_capture": _QUALITY_BUCKET,
                },
                "exit_component_quality_breakdown": {
                    "ema_cross_loss_exit": _EXIT_COMPONENT_QUALITY_BUCKET,
                },
            },
            "trade_records": [
                {
                    **_SAMPLE_REPORT_V4["variants"][0]["trade_records"][0],
                    "exit_reason": "signal:ema_cross",
                    "exit_component_id": "ema_cross_loss_exit",
                    "entry_price": 10000.0,
                    "exit_price": 10100.0,
                    "mfe_price": 400.0,
                    "mfe_pct": 0.04,
                    "mfe_atr": None,
                    "mae_price": -50.0,
                    "mae_pct": -0.005,
                    "mae_atr": None,
                    "bars_to_mfe": 4,
                    "bars_to_mae": 1,
                    "captured_price": 100.0,
                    "captured_pct": 0.01,
                    "captured_atr": None,
                    "capture_ratio": 0.25,
                    "giveback_price": 300.0,
                    "giveback_pct": 0.03,
                    "giveback_atr": None,
                    "bars_from_mfe_to_exit": 2,
                    "quality_flags": ["high_mfe_low_capture", "signal_exit_giveback_failure"],
                }
            ],
        }
    ],
}


def _write_artifacts(
    results_dir: Path,
    *,
    schema_version: int = 3,
    payload: dict | None = None,
) -> str:
    if payload is None:
        payload = {**_SAMPLE_REPORT, "report_schema_version": schema_version}
    else:
        payload = {**payload, "report_schema_version": schema_version}
    run_id = str(payload["run_id"])
    runs = results_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    (runs / f"{run_id}.json").write_text(text, encoding="utf-8")
    (results_dir / "latest.json").write_text(text, encoding="utf-8")
    return run_id


def test_list_and_load_run(tmp_path: Path) -> None:
    run_id = _write_artifacts(tmp_path)
    summaries = list_run_summaries(results_dir=tmp_path)
    assert len(summaries) == 1
    assert summaries[0].run_id == run_id

    report = load_run_report(run_id=run_id, results_dir=tmp_path)
    assert report.report_schema_version == 3
    assert report.variants[0].trade_overlays[0].exit_reason == "stop_loss:sl1"


def test_load_schema_v4_report(tmp_path: Path) -> None:
    run_id = _write_artifacts(tmp_path, payload=_SAMPLE_REPORT_V4, schema_version=4)
    report = parse_run_report(json.loads((tmp_path / "runs" / f"{run_id}.json").read_text(encoding="utf-8")))
    assert report.report_schema_version == 4

    variant = report.variants[0]
    assert variant.metrics.profile_breakdown is not None
    aligned = variant.metrics.profile_breakdown["aligned"]
    assert aligned.gross_pnl == 10.0
    assert aligned.fees_paid == 1.0
    assert aligned.avg_return_pct == 0.09
    assert aligned.exit_reason_mix == {"signal:rsi_exit": 1}

    assert variant.metrics.exit_reason_breakdown is not None
    reason_bucket = variant.metrics.exit_reason_breakdown["signal:rsi_exit"]
    assert reason_bucket.avg_hold_bars == 3.0
    assert not hasattr(reason_bucket, "exit_reason_mix")

    fee = variant.metrics.fee_diagnostics
    assert fee is not None
    assert fee.fees_rate == 0.0006
    assert fee.net_pnl == 9.0

    trade = variant.trade_records[0]
    assert trade.entry_profile == "aligned"
    assert trade.active_exit_profile == "aligned"
    assert trade.exit_profile == "aligned"
    assert trade.gross_pnl == 10.0
    assert trade.hold_bars == 3

    report_from_disk = load_run_report(run_id=run_id, results_dir=tmp_path)
    assert report_from_disk.model_dump() == report.model_dump()


def test_load_schema_v5_report_with_trade_quality_diagnostics(tmp_path: Path) -> None:
    run_id = _write_artifacts(tmp_path, payload=_SAMPLE_REPORT_V5, schema_version=5)
    report = parse_run_report(json.loads((tmp_path / "runs" / f"{run_id}.json").read_text(encoding="utf-8")))
    assert report.report_schema_version == 5
    assert report.trade_quality_config is not None
    assert report.trade_quality_config.schema_ == "trade-exit-quality-diagnostics-v1"
    assert report.trade_quality_config.atr_source is None

    variant = report.variants[0]
    assert variant.metrics.profile_side_breakdown is not None
    assert variant.metrics.profile_side_breakdown.long.aligned.trades == 1
    assert variant.metrics.profile_side_breakdown.total.total.pnl == 9.0
    assert variant.metrics.profile_side_breakdown.short.total.trades == 0

    assert variant.metrics.quality_flag_breakdown is not None
    flag_bucket = variant.metrics.quality_flag_breakdown["high_mfe_low_capture"]
    assert flag_bucket.avg_mfe_atr is None
    assert flag_bucket.avg_capture_ratio == 0.25
    assert variant.metrics.exit_component_quality_breakdown is not None
    component = variant.metrics.exit_component_quality_breakdown["ema_cross_loss_exit"]
    assert component.signal_exit_giveback_failures == 1

    trade = variant.trade_records[0]
    assert trade.mfe_pct == 0.04
    assert trade.mfe_atr is None
    assert trade.quality_flags == ["high_mfe_low_capture", "signal_exit_giveback_failure"]

    report_from_disk = load_run_report(run_id=run_id, results_dir=tmp_path)
    assert report_from_disk.model_dump() == report.model_dump()


def test_load_schema_v3_report_still_valid(tmp_path: Path) -> None:
    run_id = _write_artifacts(tmp_path, schema_version=3)
    report = load_run_report(run_id=run_id, results_dir=tmp_path)
    assert report.report_schema_version == 3
    assert report.variants[0].metrics.profile_breakdown is None
    assert report.variants[0].metrics.profile_side_breakdown is None
    assert report.variants[0].trade_records[0].entry_profile is None


def test_unsupported_schema_version(tmp_path: Path) -> None:
    _write_artifacts(tmp_path, schema_version=99)
    with pytest.raises(UnsupportedSchemaVersionError):
        list_run_summaries(results_dir=tmp_path)


def test_http_runs_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.results_reader as reader

    monkeypatch.setattr(reader, "default_results_dir", lambda: tmp_path)
    run_id = _write_artifacts(tmp_path)

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}

    listed = client.get("/api/research/runs")
    assert listed.status_code == 200
    assert listed.json()[0]["run_id"] == run_id

    latest = client.get("/api/research/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == run_id

    one = client.get(f"/api/research/runs/{run_id}")
    assert one.status_code == 200
    assert one.json()["variants"][0]["trade_records"][0]["exit_reason"] == "stop_loss:sl1"

    missing = client.get("/api/research/runs/does-not-exist")
    assert missing.status_code == 404


def test_validate_run_id_rejects_unsafe() -> None:
    with pytest.raises(InvalidRunIdError):
        validate_run_id("../latest")
    with pytest.raises(InvalidRunIdError):
        validate_run_id("foo/bar")
    with pytest.raises(InvalidRunIdError):
        validate_run_id("foo\\bar")


def test_http_invalid_run_id_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.results_reader as reader

    monkeypatch.setattr(reader, "default_results_dir", lambda: Path("/unused"))

    client = TestClient(app)
    # Single path segment after decode (encoded ``/`` is rejected by the ASGI stack with 404).
    for bad_id in ("%2E%2E", "foo%5Cbar", "bad%20id", "foo%40bar"):
        resp = client.get(f"/api/research/runs/{bad_id}")
        assert resp.status_code == 400, bad_id
        assert "Invalid run_id" in resp.json()["detail"]


def test_http_missing_valid_run_id_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_api.services.results_reader as reader

    monkeypatch.setattr(reader, "default_results_dir", lambda: tmp_path)

    client = TestClient(app)
    valid_missing = "2026-05-01T120000Z_ema_pullback_BTCUSDT_5m"
    resp = client.get(f"/api/research/runs/{valid_missing}")
    assert resp.status_code == 404


def test_http_get_run_summary_returns_compact_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.results_reader as reader

    monkeypatch.setattr(reader, "default_results_dir", lambda: tmp_path)
    run_id = _write_artifacts(tmp_path, payload=_SAMPLE_REPORT_V5, schema_version=6)
    variant = {
        **_SAMPLE_REPORT_V5["variants"][0],
        "metrics": {
            **_SAMPLE_REPORT_V5["variants"][0]["metrics"],
            "trade_management_summary": {
                "by_phase_reached": {"runner": {"trade_count": 1}},
            },
        },
        "trade_records_count": 1,
        "closed_trades_count": 1,
        "open_trades_count": 0,
    }
    variant.pop("trade_records", None)
    summary_payload = {
        **_SAMPLE_REPORT_V5,
        "run_id": run_id,
        "variants": [variant],
        "artifact_kind": "run_summary",
        "summary_schema_version": 1,
        "source_report_path": f"research/results/runs/{run_id}.json",
    }
    summary_payload.pop("candles", None)
    (tmp_path / "runs" / f"{run_id}.summary.json").write_text(
        json.dumps(summary_payload, indent=2),
        encoding="utf-8",
    )

    client = TestClient(app)
    resp = client.get(f"/api/research/runs/{run_id}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact_kind"] == "run_summary"
    assert "trade_management_events" not in body["variants"][0]
    assert "trade_records" not in body["variants"][0]
    assert body["variants"][0]["metrics"]["trade_management_summary"]["by_phase_reached"]["runner"][
        "trade_count"
    ] == 1


def test_http_get_managed_run_report_through_bff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_api.services.results_reader as reader

    from tests.test_research_api_run_report import (
        _managed_trade_management_block,
        _managed_trade_management_summary_fixture,
        _minimal_report_payload,
        _minimal_trade,
        _trade_management_event,
    )
    from research.strategies.ema_pullback.execution.results import (
        baseline_vs_managed_summary_placeholder,
    )

    monkeypatch.setattr(reader, "default_results_dir", lambda: tmp_path)
    payload = _minimal_report_payload(
        trade_management_events=[
            _trade_management_event(event_type="active_stop_updated", component_id="break_even_stop"),
            _trade_management_event(event_type="exit_executed", from_phase="protected", to_phase=None),
        ],
        metrics={
            **_minimal_report_payload()["variants"][0]["metrics"],  # type: ignore[index]
            "trade_management_summary": _managed_trade_management_summary_fixture(),
            "baseline_vs_managed_summary": baseline_vs_managed_summary_placeholder(),
        },
        trade_records=[_minimal_trade(trade_management=_managed_trade_management_block())],
    )
    payload["report_schema_version"] = 6
    run_id = _write_artifacts(tmp_path, payload=payload, schema_version=6)

    client = TestClient(app)
    resp = client.get(f"/api/research/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    trade_tm = body["variants"][0]["trade_records"][0]["trade_management"]
    assert trade_tm["exit_layer"] == "exit_management"
    assert trade_tm["active_stop_at_exit"] == 100.0
    assert trade_tm["managed_events"][0]["event_type"] == "active_stop_updated"
    assert body["variants"][0]["trade_management_events"][0]["event_type"] == "active_stop_updated"
    assert body["variants"][0]["metrics"].get("stop_management_breakdown") is None
    assert (
        body["variants"][0]["metrics"]["trade_management_summary"]["stop_management_breakdown"][
            "break_even_stop"
        ]["trade_count"]
        == 1
    )
    assert body["variants"][0]["metrics"]["baseline_vs_managed_summary"]["saved_by_managed_stop"] == []


def test_http_unsupported_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_api.services.results_reader as reader

    monkeypatch.setattr(reader, "default_results_dir", lambda: tmp_path)
    _write_artifacts(tmp_path, schema_version=99)

    client = TestClient(app)
    resp = client.get("/api/research/runs")
    assert resp.status_code == 422
    assert "Unsupported report_schema_version" in resp.json()["detail"]
