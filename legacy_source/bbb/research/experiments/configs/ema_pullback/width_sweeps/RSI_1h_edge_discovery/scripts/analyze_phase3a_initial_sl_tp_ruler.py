#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def parse_num(s: str) -> float:
    return float(s.replace("p", "."))


def parse_candidate_id(cid: str):
    # Extract exit params from suffix.
    m = re.search(r"_sl(base|1h)_([0-9p]+)_tp(base|1h)_([0-9p]+)_rr([0-9p]+)_", cid)
    if not m:
        raise ValueError(f"Cannot parse exits from {cid}")
    sl_tf = m.group(1)
    sl = parse_num(m.group(2))
    tp_tf = m.group(3)
    tp = parse_num(m.group(4))
    rr = parse_num(m.group(5))

    if "old_litmus_exact" in cid:
        group = "old_litmus_exact"
    elif "current_litmus_exact" in cid:
        group = "current_litmus_exact"
    elif "base_atr_sl_tp_ratio_sweep" in cid:
        group = "base_atr_ratio_sweep"
    elif "base_atr_sl_tp_exact_tp_sweep" in cid:
        group = "base_atr_exact_tp_sweep"
    elif "oneh_atr_sl_tp_ratio_sweep" in cid:
        group = "oneh_atr_ratio_sweep"
    elif "oneh_atr_sl_tp_anchor_sweep" in cid:
        group = "oneh_atr_anchor_sweep"
    elif "cross_base_sl_oneh_tp_sweep" in cid:
        group = "cross_base_sl_oneh_tp"
    elif "cross_oneh_sl_base_tp_sweep" in cid:
        group = "cross_oneh_sl_base_tp"
    else:
        group = "unknown"

    return group, sl_tf, sl, tp_tf, tp, rr


def main(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for item in payload["results"]:
        group, sl_tf, sl, tp_tf, tp, rr = parse_candidate_id(item["candidate_id"])
        long_pf = item.get("long_profit_factor")
        short_pf = item.get("short_profit_factor")
        rows.append({
            "candidate_id": item["candidate_id"],
            "group": group,
            "sl_atr_timeframe": sl_tf,
            "sl_atr_multiplier": sl,
            "tp_atr_timeframe": tp_tf,
            "tp_atr_multiplier": tp,
            "rr_ratio": rr,
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
            "both_sides_pf_gt_1": bool(long_pf and short_pf and long_pf > 1 and short_pf > 1),
            "fees_paid": item["fees_paid"],
            "stop_loss_after_bad_context": item.get("stop_loss_after_bad_context"),
            "stop_loss_after_low_mfe": item.get("stop_loss_after_low_mfe"),
        })

    df = pd.DataFrame(rows)
    df["main_acceptance"] = (
        (df["trades"] >= 100)
        & (df["profit_factor"] >= 1.18)
        & (df["long_profit_factor"] > 1.10)
        & (df["short_profit_factor"] > 1.10)
        & (df["pf_symmetry_gap"] <= 0.30)
        & (df["rr_ratio"] >= 2.25)
    )

    scored = df[(df["trades"] >= 80) & (df["both_sides_pf_gt_1"]) & (df["rr_ratio"] >= 2.0)].copy()
    if not scored.empty:
        def norm(s):
            return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else 0.0
        scored["wr_score"] = norm(scored["win_rate_pct"])
        scored["pf_score"] = norm(scored["profit_factor"])
        scored["sample_score"] = np.minimum(scored["trades"] / 220.0, 1.0)
        scored["symmetry_score"] = np.clip(1.0 - scored["pf_symmetry_gap"] / 0.30, 0, 1)
        scored["dd_score"] = norm(scored["max_drawdown_pct"])
        scored["main_score"] = 100 * (
            0.26 * scored["wr_score"]
            + 0.25 * scored["pf_score"]
            + 0.25 * scored["symmetry_score"]
            + 0.14 * scored["sample_score"]
            + 0.10 * scored["dd_score"]
        )
        df = df.merge(scored[["candidate_id", "main_score"]], on="candidate_id", how="left")
    else:
        df["main_score"] = 0.0

    df["main_score"] = df["main_score"].fillna(0.0)

    out_dir = Path(path).with_suffix("").parent / "phase3a_initial_sl_tp_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_dir / "phase3a_parsed_results.csv", index=False)
    df.sort_values(["main_score", "profit_factor", "pnl"], ascending=False).to_csv(out_dir / "phase3a_ranked_main_score.csv", index=False)
    df[df["main_acceptance"]].sort_values(["main_score", "profit_factor"], ascending=False).to_csv(out_dir / "phase3a_accepted_candidates.csv", index=False)
    df[df["group"].eq("old_litmus_exact")].to_csv(out_dir / "phase3a_old_litmus_exact.csv", index=False)
    df[df["sl_atr_timeframe"].eq("base") & df["tp_atr_timeframe"].eq("base")].sort_values(["main_score", "profit_factor"], ascending=False).to_csv(out_dir / "phase3a_best_base_atr.csv", index=False)
    df[df["sl_atr_timeframe"].eq("1h") & df["tp_atr_timeframe"].eq("1h")].sort_values(["main_score", "profit_factor"], ascending=False).to_csv(out_dir / "phase3a_best_1h_atr.csv", index=False)
    df[df["sl_atr_timeframe"].ne(df["tp_atr_timeframe"])].sort_values(["main_score", "profit_factor"], ascending=False).to_csv(out_dir / "phase3a_best_cross_ruler.csv", index=False)

    print(f"Wrote analysis to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: analyze_phase3a_initial_sl_tp_ruler.py path/to/summary.json")
    main(sys.argv[1])
