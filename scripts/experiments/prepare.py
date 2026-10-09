"""One-time preparation of historical Experiment data (not runtime; read-only by default).

Subcommands (all dry-run unless `--apply` is given where applicable):

  inventory   report of run bundles under the research data root and the planned moves of the
              runs referenced by the two EMA500 result tables into <artifacts_root>/<run_id>
  normalize   rename the planned bundles into <artifacts_root>/<run_id> (dry-run; --apply writes a rollback journal)
  links       classify (run, row) pairs of the trailing experiment: CONFIRMED / POSSIBLE / NO LINK
              (migration vocabulary only; the runtime knows only an optional `run_id`)
  prepare     write manifest `result_schema` (+ `view`), `experiments.json` and the trailing
              `run_id` column (dry-run prints the plan; `--apply` writes with backups)
  verify      parity checks after preparation

Nothing here moves or deletes run bundles.  Cleanup is a separate, manually approved step.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RUN_DIR = re.compile(r"run_[0-9a-f]{32}$")
EMA500 = "BTCUSDT.P/ema500"
RATIO = f"{EMA500}/width_x_untouched_x_stop_x_ratio_4d"
TRAIL = f"{EMA500}/width_x_untouched_x_stop_x_trailing_geometry_4d"
NET_TOLERANCE = 0.01


# ----------------------------------------------------------------------------- bundles

def find_bundles(*roots: Path) -> dict[str, list[Path]]:
    """run_id (folder name) -> real directories of run bundles, symlinks collapsed."""
    found: dict[str, set[Path]] = defaultdict(set)
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            name = os.path.basename(dirpath)
            if RUN_DIR.match(name) and "manifest.json" in filenames:
                found[name].add(Path(os.path.realpath(dirpath)))
                dirnames[:] = []
    return {k: sorted(v) for k, v in found.items()}


def manifest_hash(bundle: Path) -> str:
    return hashlib.sha256((bundle / "manifest.json").read_bytes()).hexdigest()


def table_run_ids(table: Path) -> list[str]:
    with table.open(newline="") as fh:
        return [r["run_id"] for r in csv.DictReader(fh) if r.get("run_id")]


def inventory(data_root: Path, artifacts_root: Path | None = None) -> dict[str, Any]:
    artifacts = artifacts_root or data_root / "runs"
    bundles = find_bundles(artifacts, data_root / "analysis")
    referenced: dict[str, str] = {}
    for rel in (RATIO,):
        for rid in table_run_ids(data_root / "analysis" / rel / "runs.csv"):
            referenced[rid] = rel
    plan, stop = [], []
    for rid, dirs in sorted(bundles.items()):
        if rid not in referenced:
            continue
        hashes = {manifest_hash(d) for d in dirs}
        body = {"run_id": rid, "copies": [str(d) for d in dirs]}
        manifest = json.loads((dirs[0] / "manifest.json").read_text())
        if manifest.get("run_id") != rid:
            stop.append({**body, "reason": "folder name differs from manifest.run_id"})
            continue
        if len(hashes) > 1:
            stop.append({**body, "reason": "copies with different manifests"})
            continue
        target = artifacts / rid
        in_place = any(d == target.resolve() for d in dirs)
        source = target if in_place else dirs[0]
        same_volume = os.stat(source).st_dev == os.stat(artifacts).st_dev
        plan.append({**body, "target": str(target), "already_canonical": in_place,
                     "identical_duplicates": max(0, len(dirs) - 1), "same_volume": same_volume})
    missing = sorted(set(referenced) - set(bundles))
    return {
        "bundles_found": len(bundles),
        "referenced_run_ids": len(referenced),
        "referenced_missing_everywhere": missing,
        "planned_moves": [p for p in plan if not p["already_canonical"]],
        "already_canonical": sum(1 for p in plan if p["already_canonical"]),
        "stop": stop,
        "ok_to_proceed": not stop and not missing and all(p["same_volume"] for p in plan),
    }


def normalize(data_root: Path, apply: bool, journal: Path | None = None) -> dict[str, Any]:
    """Rename referenced bundles into <artifacts_root>/<run_id> with a recoverable journal.

    Dry-run unless `apply`.  Refuses when the inventory says STOP/missing/other volume.  All
    sources and targets are checked before the first rename; the journal (one JSON line per
    move) is created before the first rename and flushed after every successful move, so a
    failure after N moves leaves a journal that `rollback` can use.  Identical duplicates stay
    in place (removed only by the separate cleanup step).
    """
    report = inventory(data_root)
    if not report["ok_to_proceed"]:
        return {"refused": True, "reason": "inventory is not clean", "stop": report["stop"][:20],
                "missing": report["referenced_missing_everywhere"][:20]}
    moves = [(Path(m["copies"][0]), Path(m["target"])) for m in report["planned_moves"]]
    bad = [str(d) for s, d in moves if not s.is_dir() or d.exists()]
    if bad:
        return {"refused": True, "reason": "preflight failed (source missing or target exists)",
                "examples": bad[:20]}
    path = journal or data_root / "normalize_journal.jsonl"
    if apply:
        if path.exists():
            return {"refused": True, "reason": f"journal already exists: {path}"}
        with path.open("w") as fh:
            fh.flush()
            os.fsync(fh.fileno())
            for src, dst in moves:
                os.rename(src, dst)
                fh.write(json.dumps({"from": str(src), "to": str(dst)}) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
    return {"applied": apply, "moves": len(moves), "journal": str(path) if apply else None}


def rollback(journal: Path) -> int:
    done = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    for m in reversed(done):
        os.rename(m["to"], m["from"])
    return len(done)


# ----------------------------------------------------------------------------- links

def spec_dimensions(request: dict[str, Any]) -> dict[str, float] | None:
    """Dimension values a run's own recorded strategy spec declares, or None if unreadable."""
    try:
        spec = request["strategy"]["raw_spec"]
        stop = spec["trade_management"]["exit_management"]["stop_management"][0]["params"]
        exit_ = spec["trade_management"]["exit_policy"]["always_on"]["exits"][0]
        return {
            "width": float(spec["setups"][0]["params"]["min_current_width_atr"]),
            "lookback": float(spec["setups"][1]["params"]["lookback"]),
            "sl": float(exit_["distance"]["multiplier"]),
            "trigger_r": float(stop["trigger_r"]),
            "distance_r": float(stop["trail_distance_r"]),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6


def classify(run_dims: dict[str, float] | None, run_metrics: dict[str, Any],
             row: dict[str, str], row_market_hash: str | None, run_market_hash: str | None) -> str:
    """CONFIRMED / POSSIBLE / NO LINK for one (run, row) pair."""
    if run_dims is None:
        return "POSSIBLE"
    sl = run_dims["sl"]
    if row["geometry_grid_unit"] == "R":
        dims_ok = (_close(float(row["trigger_r"]), run_dims["trigger_r"])
                   and _close(float(row["trail_distance_r"]), run_dims["distance_r"]))
    else:
        dims_ok = (_close(float(row["trail_trigger_atr"]), run_dims["trigger_r"] * sl)
                   and _close(float(row["trail_distance_atr"]), run_dims["distance_r"] * sl))
    dims_ok = dims_ok and _close(float(row["min_current_width_atr"]), run_dims["width"]) \
        and _close(float(row["untouched_lookback"]), run_dims["lookback"]) \
        and _close(float(row["sl_atr_multiplier"]), sl)
    if not dims_ok:
        return "NO LINK"
    metrics_ok = (int(row["realised_trade_count"]) == int(run_metrics["realised_trade_count"])
                  and int(row["open_position_count"]) == int(run_metrics["open_position_count"])
                  and abs(float(row["net_pnl"]) - float(run_metrics["net_pnl"])) <= NET_TOLERANCE)
    if not metrics_ok:
        return "NO LINK"
    if row_market_hash is not None and row_market_hash != run_market_hash:
        return "NO LINK"
    return "CONFIRMED"


def plan_links(data_root: Path) -> dict[str, Any]:
    exp = data_root / "analysis" / TRAIL
    rows = []
    with (exp / "runs.csv").open(newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            if r["arm"] == "trailing_no_tp":
                rows.append((i, r))
    index: dict[tuple[float, float, float], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for i, r in rows:
        index[(float(r["min_current_width_atr"]), float(r["untouched_lookback"]),
               float(r["sl_atr_multiplier"]))].append((i, r))
    bundles = find_bundles(exp / "runs")
    confirmed: dict[int, list[str]] = defaultdict(list)
    report = {"runs_examined": len(bundles), "no_row": [], "no_link": [], "possible": [], "confirmed": {}}
    for rid, dirs in sorted(bundles.items()):
        b = dirs[0]
        dims = spec_dimensions(json.loads((b / "request.json").read_text()))
        metrics = json.loads((b / "metrics.json").read_text())
        mhash = json.loads((b / "manifest.json").read_text()).get("market_data_hash")
        if dims is None:
            report["possible"].append({"run_id": rid, "reason": "spec dimensions unreadable"})
            continue
        cand = index.get((dims["width"], dims["lookback"], dims["sl"]), [])
        classes = [(i, classify(dims, metrics, r, r.get("market_data_hash"), mhash)) for i, r in cand]
        hits = [i for i, c in classes if c == "CONFIRMED"]
        if hits:
            for i in hits:
                confirmed[i].append(rid)
        elif any(True for _ in cand):
            report["no_link"].append({"run_id": rid, "reason": "no row with equal dimensions and metrics"})
        else:
            report["no_row"].append(rid)
    for i, runs in sorted(confirmed.items()):
        if len(runs) == 1:
            report["confirmed"][str(i)] = runs[0]
        else:
            report["possible"].append({"row_index": i, "runs": runs,
                                       "reason": "several runs confirmed for one row"})
    report["summary"] = {k: len(v) for k, v in report.items() if isinstance(v, (list, dict))}
    return report


# ----------------------------------------------------------------------------- prepare

SCHEMAS: dict[str, dict[str, Any]] = {
    RATIO: {
        "experiment_id": "btcusdt_p.ema500.ratio_4d",
        "result_schema": {
            "contract_version": "research_experiment_result_schema.v1",
            "table": "runs.csv", "run_id_column": "run_id", "provenance": {"value": "engine"},
            "row_columns": {"market_data_hash": "market_data_hash"},
            "dimensions": [
                {"id": "width", "label": "Stack width", "column": "min_current_width_atr", "unit": "ATR"},
                {"id": "lookback", "label": "Untouched lookback", "column": "untouched_lookback", "unit": "bars"},
                {"id": "sl", "label": "Initial SL", "column": "sl_atr_multiplier", "unit": "ATR"},
                {"id": "tp_ratio", "label": "TP / SL", "column": "tp_sl_ratio", "unit": "R"},
            ],
            "metrics": [
                {"column": "return_pct", "label": "Return", "format": "fraction"},
                {"column": "profit_factor", "label": "PF", "format": "number"},
                {"column": "max_drawdown_pct", "label": "Max DD", "format": "fraction"},
                {"column": "cumulative_net_r", "label": "Cum. R", "format": "number", "unit": "R"},
                {"column": "realised_trade_count", "label": "Trades", "format": "integer"},
                {"column": "long_cumulative_net_r", "label": "Long R", "format": "number", "unit": "R"},
                {"column": "short_cumulative_net_r", "label": "Short R", "format": "number", "unit": "R"},
            ],
            "view": [{"id": "main", "x": "lookback", "y": "width", "controls": ["sl", "tp_ratio"],
                      "default_metric": "return_pct"}],
        },
        "registry": {"title": "EMA500 · fixed SL × TP ratio", "ticker": "BTCUSDT.P", "anchor": "EMA500"},
    },
    TRAIL: {
        "experiment_id": "btcusdt_p.ema500.trailing_geometry_4d",
        "result_schema": {
            "contract_version": "research_experiment_result_schema.v1",
            "table": "runs.csv", "run_id_column": "run_id", "provenance": {"value": "replay"},
            "dimensions": [
                {"id": "width", "label": "Stack width", "column": "min_current_width_atr", "unit": "ATR"},
                {"id": "lookback", "label": "Untouched lookback", "column": "untouched_lookback", "unit": "bars"},
                {"id": "sl", "label": "Initial SL", "column": "sl_atr_multiplier", "unit": "ATR"},
                {"id": "trigger", "label": "Trigger T", "grid_column": "geometry_grid_unit",
                 "grids": {"ATR": {"column": "trail_trigger_atr", "unit": "ATR"},
                           "R": {"column": "trigger_r", "unit": "R"}}},
                {"id": "distance", "label": "Trail D", "grid_column": "geometry_grid_unit",
                 "grids": {"ATR": {"column": "trail_distance_atr", "unit": "ATR"},
                           "R": {"column": "trail_distance_r", "unit": "R"}}},
            ],
            "metrics": [
                {"column": "net_pnl", "label": "Net PnL", "format": "number", "unit": "USDT"},
                {"column": "return_pct", "label": "Return", "format": "fraction"},
                {"column": "profit_factor", "label": "PF", "format": "number"},
                {"column": "max_drawdown_pct", "label": "Max DD", "format": "fraction"},
                {"column": "cumulative_net_r", "label": "Cum. R", "format": "number", "unit": "R"},
                {"column": "realised_trade_count", "label": "Trades", "format": "integer"},
                {"column": "long_net_pnl", "label": "Long net", "format": "number", "unit": "USDT"},
                {"column": "short_net_pnl", "label": "Short net", "format": "number", "unit": "USDT"},
                {"column": "long_cumulative_net_r", "label": "Long R", "format": "number", "unit": "R"},
                {"column": "short_cumulative_net_r", "label": "Short R", "format": "number", "unit": "R"},
            ],
            "view": [
                {"id": "cells", "x": "lookback", "y": "width",
                 "controls": ["sl", "grid", "trigger", "distance"], "default_metric": "net_pnl",
                 "filmstrip": "trigger"},
                {"id": "geometry", "x": "distance", "y": "trigger", "controls": ["sl", "grid"],
                 "aggregate_over": ["width", "lookback"], "default_metric": "net_pnl"},
            ],
        },
        "registry": {"title": "EMA500 · trailing geometry (no TP)", "ticker": "BTCUSDT.P", "anchor": "EMA500"},
    },
}


def check_links_report(links: Any, table: Path) -> str | None:
    """Return a problem description, or None when the report can be written into the table."""
    if not isinstance(links, dict) or not isinstance(links.get("confirmed"), dict) \
            or "summary" not in links:
        return "links report is not the output of the links command"
    with table.open(newline="") as fh:
        rows = {i: r for i, r in enumerate(csv.DictReader(fh))}
    for key, rid in links["confirmed"].items():
        if not (isinstance(key, str) and key.isdigit() and int(key) in rows):
            return f"links report has an invalid row index: {key!r}"
        if not (isinstance(rid, str) and RUN_DIR.match(rid)):
            return f"links report has an invalid run id: {rid!r}"
        if rows[int(key)].get("arm") != "trailing_no_tp":
            return f"links report points at a non-treatment row: {key}"
    return None


def prepare(data_root: Path, links: dict[str, Any] | None, apply: bool) -> dict[str, Any]:
    tpath0 = data_root / "analysis" / TRAIL / "runs.csv"
    with tpath0.open(newline="") as fh:
        needs_links = "run_id" not in next(csv.reader(fh))
    if apply and needs_links:
        problem = "no links report given" if links is None else check_links_report(links, tpath0)
        if problem:
            return {"refused": True, "reason": problem, "applied": False}
    analysis = data_root / "analysis"
    actions: list[str] = []
    for rel, spec in SCHEMAS.items():
        mpath = analysis / rel / "manifest.json"
        manifest = json.loads(mpath.read_text())
        if manifest.get("result_schema") == spec["result_schema"]:
            continue
        actions.append(f"manifest {rel}: add experiment_id and result_schema")
        if apply:
            shutil.copy2(mpath, mpath.with_suffix(".pre_experiment.json"))
            manifest["experiment_id"] = spec["experiment_id"]
            manifest["result_schema"] = spec["result_schema"]
            mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    registry = {"registry_version": 1, "experiments": [
        {"experiment_id": s["experiment_id"], **s["registry"], "manifest": f"{rel}/manifest.json"}
        for rel, s in SCHEMAS.items()]}
    rpath = analysis / "experiments.json"
    if not rpath.exists() or json.loads(rpath.read_text()) != registry:
        actions.append("experiments.json: write registry")
        if apply:
            rpath.write_text(json.dumps(registry, indent=2) + "\n")
    tpath = analysis / TRAIL / "runs.csv"
    with tpath.open(newline="") as fh:
        header = next(csv.reader(fh))
    if "run_id" not in header:
        n = len((links or {}).get("confirmed", {}))
        actions.append(f"trailing runs.csv: add nullable run_id column ({n} confirmed links)")
        if apply:
            confirmed = (links or {}).get("confirmed", {})
            backup = tpath.with_name("runs.pre_run_id.csv")
            shutil.copy2(tpath, backup)
            with backup.open(newline="") as src, tpath.open("w", newline="") as dst:
                r = csv.reader(src)
                w = csv.writer(dst)
                w.writerow(next(r) + ["run_id"])
                for i, row in enumerate(r):
                    w.writerow(row + [confirmed.get(str(i), "")])
    return {"applied": apply, "actions": actions}


# ----------------------------------------------------------------------------- verify

def verify(data_root: Path, artifacts_root: Path | None = None) -> dict[str, Any]:
    artifacts = artifacts_root or data_root / "runs"
    problems: list[str] = []
    for rel in SCHEMAS:
        exp = data_root / "analysis" / rel
        manifest = json.loads((exp / "manifest.json").read_text())
        if "result_schema" not in manifest:
            problems.append(f"{rel}: manifest has no result_schema")
            continue
        for rid in table_run_ids(exp / "runs.csv"):
            if not (artifacts / rid / "manifest.json").is_file():
                problems.append(f"{rel}: run {rid} has no bundle at {artifacts / rid}")
    return {"ok": not problems, "problems": problems[:50], "problem_count": len(problems)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["inventory", "normalize", "links", "prepare", "verify"])
    ap.add_argument("--data-root", type=Path, required=True, help="research data root (runs/, analysis/)")
    ap.add_argument("--apply", action="store_true", help="normalize/prepare: write changes (default is a dry run)")
    ap.add_argument("--links-report", type=Path, help="prepare only: JSON written by the links command")
    ap.add_argument("--out", type=Path, help="write the JSON report here")
    args = ap.parse_args(argv)
    if args.command == "inventory":
        out = inventory(args.data_root)
    elif args.command == "normalize":
        out = normalize(args.data_root, args.apply)
    elif args.command == "links":
        out = plan_links(args.data_root)
    elif args.command == "prepare":
        links = json.loads(args.links_report.read_text()) if args.links_report else None
        out = prepare(args.data_root, links, args.apply)
    else:
        out = verify(args.data_root)
    text = json.dumps(out, indent=2)
    refused = bool(out.get("refused"))
    if args.out:
        args.out.write_text(text + "\n")
    print(text if len(text) < 4000 else text[:4000] + "\n... (truncated; use --out)")
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
