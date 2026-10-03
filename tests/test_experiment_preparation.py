from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "experiments"))
import prepare  # noqa: E402

RID_A = "run_" + "a" * 32
RID_B = "run_" + "b" * 32
RID_C = "run_" + "c" * 32


def _request(width: float, lookback: float, sl: float, trig: float, dist: float) -> dict:
    return {"strategy": {"raw_spec": {
        "setups": [{"params": {"min_current_width_atr": width}}, {"params": {"lookback": lookback}}],
        "trade_management": {
            "exit_management": {"stop_management": [{"params": {"trigger_r": trig, "trail_distance_r": dist}}]},
            "exit_policy": {"always_on": {"exits": [{"distance": {"multiplier": sl}}]}},
        },
    }}}


def _bundle(root: Path, rid: str, request: dict, trades: int, net: str, market: str = "h") -> Path:
    d = root / rid
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"run_id": rid, "market_data_hash": market}))
    (d / "request.json").write_text(json.dumps(request))
    (d / "metrics.json").write_text(json.dumps(
        {"realised_trade_count": trades, "open_position_count": 0, "net_pnl": net}))
    return d


def _row(**kw: object) -> dict[str, str]:
    base = {"arm": "trailing_no_tp", "geometry_grid_unit": "R", "min_current_width_atr": "4",
            "untouched_lookback": "80", "sl_atr_multiplier": "3", "trigger_r": "12",
            "trail_distance_r": "6", "trail_trigger_atr": "36", "trail_distance_atr": "18",
            "realised_trade_count": "10", "open_position_count": "0", "net_pnl": "100.0"}
    base.update({k: str(v) for k, v in kw.items()})
    return base


def test_classify_confirmed_possible_and_no_link() -> None:
    dims = prepare.spec_dimensions(_request(4, 80, 3, 12, 6))
    metrics = {"realised_trade_count": 10, "open_position_count": 0, "net_pnl": "100.001"}
    assert prepare.classify(dims, metrics, _row(), None, "x") == "CONFIRMED"
    assert prepare.classify(None, metrics, _row(), None, "x") == "POSSIBLE"
    assert prepare.classify(dims, {**metrics, "realised_trade_count": 11}, _row(), None, "x") == "NO LINK"
    assert prepare.classify(dims, metrics, _row(trigger_r=13), None, "x") == "NO LINK"
    # ATR-grid row: the same run is compared through trigger_r * SL
    atr = _row(geometry_grid_unit="ATR", trail_trigger_atr=36, trail_distance_atr=18, trigger_r=12.0)
    assert prepare.classify(dims, metrics, atr, None, "x") == "CONFIRMED"
    # market hash only matters when the row carries one
    assert prepare.classify(dims, metrics, _row(), "other", "x") == "NO LINK"
    assert prepare.classify(dims, metrics, _row(), "x", "x") == "CONFIRMED"


def _research_root(tmp_path: Path) -> Path:
    root = tmp_path / "research"
    exp = root / "analysis" / prepare.TRAIL
    exp.mkdir(parents=True)
    cols = ["arm", "geometry_grid_unit", "min_current_width_atr", "untouched_lookback",
            "sl_atr_multiplier", "trail_trigger_atr", "trail_distance_atr", "trigger_r",
            "trail_distance_r", "realised_trade_count", "open_position_count", "net_pnl"]
    rows = [_row(), _row(trigger_r=7, trail_trigger_atr=21, realised_trade_count=5, net_pnl=50),
            _row(arm="control_tp5r", geometry_grid_unit="")]
    with (exp / "runs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (exp / "manifest.json").write_text(json.dumps({"test_id": "t"}))
    runs = exp / "runs" / "batch"
    _bundle(runs, RID_A, _request(4, 80, 3, 12, 6), 10, "100.0")
    _bundle(runs, RID_B, _request(4, 80, 3, 7, 6), 99, "1.0")  # dims match row 2? trigger 7 but numbers differ
    _bundle(runs, RID_C, _request(9, 80, 3, 12, 6), 10, "100.0")  # no row at all
    ratio = root / "analysis" / prepare.RATIO
    ratio.mkdir(parents=True)
    (ratio / "runs.csv").write_text("run_id\n")
    (ratio / "manifest.json").write_text(json.dumps({"test_id": "r"}))
    (root / "runs").mkdir()
    return root


def test_link_plan_writes_only_confirmed_unique_links(tmp_path: Path) -> None:
    report = prepare.plan_links(_research_root(tmp_path))
    assert report["confirmed"] == {"0": RID_A}
    assert report["no_link"][0]["run_id"] == RID_B
    assert report["no_row"] == [RID_C]


def test_two_confirmed_runs_for_one_row_stay_unlinked(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    _bundle(root / "analysis" / prepare.TRAIL / "runs" / "batch2",
            "run_" + "d" * 32, _request(4, 80, 3, 12, 6), 10, "100.0")
    report = prepare.plan_links(root)
    assert report["confirmed"] == {}
    assert report["possible"][0]["row_index"] == 0 and len(report["possible"][0]["runs"]) == 2


def test_prepare_is_dry_by_default_and_apply_backs_up(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    before = (root / "analysis" / prepare.TRAIL / "runs.csv").read_text()
    dry = prepare.prepare(root, {"confirmed": {"0": RID_A}, "summary": {}}, apply=False)
    assert dry["actions"] and not (root / "analysis" / "experiments.json").exists()
    assert (root / "analysis" / prepare.TRAIL / "runs.csv").read_text() == before
    prepare.prepare(root, {"confirmed": {"0": RID_A}, "summary": {}}, apply=True)
    table = list(csv.DictReader((root / "analysis" / prepare.TRAIL / "runs.csv").open()))
    assert [r["run_id"] for r in table] == [RID_A, "", ""]
    assert all(r["net_pnl"] for r in table)  # existing values untouched
    assert (root / "analysis" / prepare.TRAIL / "runs.pre_run_id.csv").read_text() == before
    assert json.loads((root / "analysis" / "experiments.json").read_text())["experiments"]
    assert prepare.prepare(root, None, apply=False)["actions"] == []  # idempotent


def test_inventory_stops_on_conflicting_copies_and_reports_moves(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    ratio = root / "analysis" / prepare.RATIO
    (ratio / "runs.csv").write_text(f"run_id\n{RID_A}\n{RID_B}\n")
    _bundle(ratio / "runs" / "b1", RID_A, {}, 1, "1")
    _bundle(ratio / "runs" / "b2", RID_A, {"x": 1}, 1, "1", market="other")  # same id, other manifest
    _bundle(ratio / "runs" / "b1", RID_B, {}, 1, "1")
    report = prepare.inventory(root)
    assert [s["run_id"] for s in report["stop"]] == [RID_A]
    assert [m["run_id"] for m in report["planned_moves"]] == [RID_B]
    assert report["ok_to_proceed"] is False
    assert not (root / "runs" / RID_B).exists()  # inventory never moves anything


def test_normalize_dry_run_apply_and_rollback(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    ratio = root / "analysis" / prepare.RATIO
    (ratio / "runs.csv").write_text(f"run_id\n{RID_A}\n")
    src = _bundle(ratio / "runs" / "b1", RID_A, {}, 1, "1")
    dry = prepare.normalize(root, apply=False)
    assert dry["moves"] == 1 and src.exists() and not (root / "runs" / RID_A).exists()
    journal = root / "j.jsonl"
    prepare.normalize(root, apply=True, journal=journal)
    assert (root / "runs" / RID_A / "manifest.json").is_file() and not src.exists()
    assert prepare.rollback(journal) == 1 and src.exists() and not (root / "runs" / RID_A).exists()


def test_normalize_refuses_when_inventory_has_a_stop(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    ratio = root / "analysis" / prepare.RATIO
    (ratio / "runs.csv").write_text(f"run_id\n{RID_A}\n")
    _bundle(ratio / "runs" / "b1", RID_A, {}, 1, "1")
    _bundle(ratio / "runs" / "b2", RID_A, {"x": 1}, 1, "1", market="other")
    assert prepare.normalize(root, apply=True)["refused"] is True
    assert not (root / "runs" / RID_A).exists()


def _two_run_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _research_root(tmp_path)
    ratio = root / "analysis" / prepare.RATIO
    (ratio / "runs.csv").write_text(f"run_id\n{RID_A}\n{RID_B}\n")
    a = _bundle(ratio / "runs" / "b1", RID_A, {}, 1, "1")
    b = _bundle(ratio / "runs" / "b1", RID_B, {}, 1, "1")
    return root, a, b


def test_normalize_failure_midway_leaves_a_recoverable_journal(tmp_path: Path, monkeypatch) -> None:
    import os

    import pytest

    root, a, b = _two_run_root(tmp_path)
    real = os.rename
    calls = {"n": 0}

    def flaky(src, dst):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("boom")
        return real(src, dst)

    monkeypatch.setattr(prepare.os, "rename", flaky)
    journal = root / "j.jsonl"
    with pytest.raises(OSError):
        prepare.normalize(root, apply=True, journal=journal)
    monkeypatch.setattr(prepare.os, "rename", real)
    assert len(journal.read_text().splitlines()) == 1  # the first move was journaled
    assert prepare.rollback(journal) == 1
    assert a.exists() and b.exists()
    assert not (root / "runs" / RID_A).exists() and not (root / "runs" / RID_B).exists()


def test_normalize_preflight_refuses_when_a_target_exists(tmp_path: Path) -> None:
    root, a, _ = _two_run_root(tmp_path)
    (root / "runs" / RID_B).mkdir()
    out = prepare.normalize(root, apply=True)
    assert out["refused"] is True and a.exists()
    assert not (root / "normalize_journal.jsonl").exists()


def _snapshot(root: Path) -> dict[str, str]:
    return {str(p): p.read_text() for p in sorted((root / "analysis").rglob("*")) if p.is_file()}


def test_prepare_apply_refuses_without_or_with_bad_links_report(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    before = _snapshot(root)
    for bad in (None, {}, {"confirmed": {}}, {"confirmed": {"0": "nope"}, "summary": {}},
                {"confirmed": {"99": RID_A}, "summary": {}},
                {"confirmed": {"2": RID_A}, "summary": {}}):  # row 2 is a control row
        out = prepare.prepare(root, bad, apply=True)  # type: ignore[arg-type]
        assert out["refused"] is True
        assert _snapshot(root) == before
    assert prepare.prepare(root, None, apply=False)["actions"]  # dry-run stays allowed


def test_prepare_cli_exits_nonzero_when_refused(tmp_path: Path) -> None:
    root = _research_root(tmp_path)
    assert prepare.main(["prepare", "--data-root", str(root), "--apply"]) == 2
