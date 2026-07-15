#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd


def parse_candidate_id(cid: str):
    if "_initial_control_" in cid:
        fav_id = cid.removeprefix("phase3b_").removesuffix("_initial_control_fee04")
        return fav_id, "initial_control", None, "initial_control"

    m = re.match(r"phase3b_(.+)_adx(40|45)_(runner_.+)_fee04$", cid)
    if not m:
        raise ValueError(f"Cannot parse candidate_id: {cid}")
    return m.group(1), "managed_runner", int(m.group(2)), m.group(3)


def main(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for item in payload["results"]:
        fav_id, run_kind, adx, profile = parse_candidate_id(item["candidate_id"])
        long_pf = item.get("long_profit_factor")
        short_pf = item.get("short_profit_factor")
        rows.append({
            "candidate_id": item["candidate_id"],
            "favorite_id": fav_id,
            "run_kind": run_kind,
            "adx_threshold": adx,
            "exit_profile": profile,
            "trades": item["total_trades"],
            "pnl": item["pnl"],
            "profit_factor": item["profit_factor"],
            "win_rate_pct": item["win_rate"] * 100,
            "max_drawdown_pct": item["max_drawdown"] * 100,
            "long_trades": item["long_trades"],
            "long_pnl": item["long_pnl"],
            "long_profit_factor": long_pf,
            "short_trades": item["short_trades"],
            "short_pnl": item["short_pnl"],
            "short_profit_factor": short_pf,
            "pf_symmetry_gap": abs((long_pf or 0) - (short_pf or 0)),
            "high_mfe_high_capture_count": item.get("high_mfe_high_capture_count"),
            "high_mfe_low_capture_count": item.get("high_mfe_low_capture_count"),
            "signal_exit_winners": item.get("signal_exit_winners"),
            "signal_exit_giveback_failures": item.get("signal_exit_giveback_failures"),
            "stop_loss_after_low_mfe": item.get("stop_loss_after_low_mfe"),
            "stop_loss_after_bad_context": item.get("stop_loss_after_bad_context"),
            "run_id": item.get("run_id"),
            "report_path": item.get("report_path"),
        })

    df = pd.DataFrame(rows)
    controls = df[df["run_kind"] == "initial_control"].set_index("favorite_id")
    managed = df[df["run_kind"] == "managed_runner"].copy()

    for metric in ["pnl", "profit_factor", "win_rate_pct", "max_drawdown_pct", "long_profit_factor", "short_profit_factor", "pf_symmetry_gap"]:
        managed[f"{metric}_initial"] = managed["favorite_id"].map(controls[metric])
        managed[f"{metric}_delta"] = managed[metric] - managed[f"{metric}_initial"]

    out_dir = Path(path).with_suffix("").parent / "phase3b_runner_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_dir / "phase3b_parsed_results.csv", index=False)
    managed.to_csv(out_dir / "phase3b_managed_with_initial_deltas.csv", index=False)

    managed.sort_values(["profit_factor_delta", "pnl_delta"], ascending=False).to_csv(out_dir / "phase3b_ranked_by_pf_delta.csv", index=False)
    managed.sort_values(["pnl_delta", "profit_factor_delta"], ascending=False).to_csv(out_dir / "phase3b_ranked_by_pnl_delta.csv", index=False)

    best_by_fav = managed.sort_values(["profit_factor_delta", "pnl_delta"], ascending=False).groupby("favorite_id", as_index=False).head(1)
    best_by_fav.to_csv(out_dir / "phase3b_best_managed_by_favorite.csv", index=False)

    by_profile = managed.groupby(["exit_profile", "adx_threshold"], dropna=False).agg(
        n=("candidate_id", "count"),
        mean_pf_delta=("profit_factor_delta", "mean"),
        median_pf_delta=("profit_factor_delta", "median"),
        mean_pnl_delta=("pnl_delta", "mean"),
        median_pnl_delta=("pnl_delta", "median"),
        mean_gap_delta=("pf_symmetry_gap_delta", "mean"),
        median_gap_delta=("pf_symmetry_gap_delta", "median"),
        improved_pf=("profit_factor_delta", lambda s: int((s > 0).sum())),
        improved_pnl=("pnl_delta", lambda s: int((s > 0).sum())),
    ).reset_index()
    by_profile.to_csv(out_dir / "phase3b_aggregate_by_exit_profile_adx.csv", index=False)

    print(f"Wrote analysis to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: analyze_phase3b_runner_rsi_ema.py path/to/summary.json")
    main(sys.argv[1])
