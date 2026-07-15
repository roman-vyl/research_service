#!/usr/bin/env python
from __future__ import annotations
import json, re, sys
from pathlib import Path
import pandas as pd
import numpy as np

def parse_candidate_id(cid: str):
    group = "base_control" if "base_control" in cid else ("transition_tail" if "transition_tail" in cid else "broad_1h")
    tf = "base" if group == "base_control" else "1h"
    m = re.search(r"_w([0-9p]+)_r([0-9p]+)_lb(\d+)", cid)
    if not m:
        raise ValueError(f"Cannot parse {cid}")
    w = float(m.group(1).replace("p", "."))
    r = float(m.group(2).replace("p", "."))
    lb = int(m.group(3))
    rm = re.search(r"_(semantic_primary_215|semantic_upper_235|transition_245)_", cid)
    if rm:
        rail = {"semantic_primary_215": 2.15, "semantic_upper_235": 2.35, "transition_245": 2.45}[rm.group(1)]
    else:
        sm = re.search(r"_sl([0-9p]+)_tp", cid)
        rail = float(sm.group(1).replace("p", "."))
    return group, tf, rail, w, r, r - w, lb

def main(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for item in payload["results"]:
        group, tf, rail, w, r, delta, lb = parse_candidate_id(item["candidate_id"])
        long_pf = item.get("long_profit_factor")
        short_pf = item.get("short_profit_factor")
        rows.append({
            "candidate_id": item["candidate_id"],
            "group": group,
            "width_atr_timeframe": tf,
            "rail": rail,
            "current_width": w,
            "recent_width": r,
            "recent_delta": delta,
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
    out_dir = Path(path).with_suffix("").parent / "phase2d_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "phase2d_parsed_results.csv", index=False)
    scored = df[(df["trades"] >= 80) & (df["both_sides_pf_gt_1"])].copy()
    if not scored.empty:
        def norm(s):
            return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else 0.0
        scored["wr_score"] = norm(scored["win_rate_pct"])
        scored["pf_score"] = norm(scored["profit_factor"])
        scored["sample_score"] = np.minimum(scored["trades"] / 220.0, 1.0)
        scored["symmetry_score"] = np.clip(1.0 - scored["pf_symmetry_gap"] / 0.35, 0, 1)
        scored["stability_score"] = 100 * (0.30*scored["wr_score"] + 0.25*scored["pf_score"] + 0.25*scored["sample_score"] + 0.20*scored["symmetry_score"])
        scored.sort_values(["stability_score", "profit_factor", "pnl"], ascending=False).to_csv(out_dir / "phase2d_stability_ranked.csv", index=False)
    df.sort_values(["pnl"], ascending=False).to_csv(out_dir / "phase2d_top_pnl.csv", index=False)
    df.sort_values(["profit_factor"], ascending=False).to_csv(out_dir / "phase2d_top_pf.csv", index=False)
    df[df["trades"] >= 120].sort_values(["profit_factor", "pnl"], ascending=False).to_csv(out_dir / "phase2d_high_sample_ranked.csv", index=False)
    print(f"Wrote analysis to {out_dir}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: analyze_phase2d_broad_1h_width.py path/to/summary.json")
    main(sys.argv[1])
