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
    if "control" in cid and "_base_" in cid:
        tf = "base"
        group = "control"
        m = re.search(r"_w([0-9p]+)_r([0-9p]+)_lb(\d+)_sl([0-9p]+)_tp", cid)
        rail = parse_num(m.group(4))
        return group, tf, rail, parse_num(m.group(1)), parse_num(m.group(2)), int(m.group(3))

    tf = "1h"
    group = "focused_1h"
    m = re.search(r"_(semantic_primary_215|semantic_upper_235)_w([0-9p]+)_r([0-9p]+)_lb(\d+)_", cid)
    rail = {"semantic_primary_215": 2.15, "semantic_upper_235": 2.35}[m.group(1)]
    return group, tf, rail, parse_num(m.group(2)), parse_num(m.group(3)), int(m.group(4))


def main(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for item in payload["results"]:
        group, tf, rail, w, r, lb = parse_candidate_id(item["candidate_id"])
        long_pf = item.get("long_profit_factor")
        short_pf = item.get("short_profit_factor")
        rows.append({
            "candidate_id": item["candidate_id"],
            "group": group,
            "width_atr_timeframe": tf,
            "rail": rail,
            "current_width": w,
            "recent_width": r,
            "width_lookback": lb,
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
        (df["trades"] >= 120)
        & (df["profit_factor"] >= 1.18)
        & (df["win_rate_pct"] >= 57)
        & (df["long_profit_factor"] > 1.12)
        & (df["short_profit_factor"] > 1.12)
        & (df["pf_symmetry_gap"] <= 0.30)
    )

    scored = df[(df["trades"] >= 80) & (df["both_sides_pf_gt_1"])].copy()
    if not scored.empty:
        def norm(s):
            return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else 0.0
        scored["wr_score"] = norm(scored["win_rate_pct"])
        scored["pf_score"] = norm(scored["profit_factor"])
        scored["sample_score"] = np.minimum(scored["trades"] / 220.0, 1.0)
        scored["symmetry_score"] = np.clip(1.0 - scored["pf_symmetry_gap"] / 0.30, 0, 1)
        scored["main_score"] = 100 * (
            0.30 * scored["wr_score"]
            + 0.25 * scored["pf_score"]
            + 0.25 * scored["symmetry_score"]
            + 0.20 * scored["sample_score"]
        )
        df = df.merge(scored[["candidate_id", "main_score"]], on="candidate_id", how="left")
    else:
        df["main_score"] = 0.0

    df["main_score"] = df["main_score"].fillna(0.0)

    out_dir = Path(path).with_suffix("").parent / "phase2e_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "phase2e_parsed_results.csv", index=False)
    df.sort_values(["main_score", "profit_factor", "pnl"], ascending=False).to_csv(out_dir / "phase2e_ranked_main_score.csv", index=False)
    df[df["main_acceptance"]].sort_values(["main_score", "profit_factor"], ascending=False).to_csv(out_dir / "phase2e_accepted_candidates.csv", index=False)
    df.sort_values("pnl", ascending=False).to_csv(out_dir / "phase2e_top_pnl.csv", index=False)

    print(f"Wrote analysis to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: analyze_phase2e_focused_1h_width.py path/to/summary.json")
    main(sys.argv[1])
