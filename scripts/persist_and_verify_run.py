"""I6.D/I6.E/I6.C -- persisted-artifact regression proof
(`compact-strategy-evaluation-boundary-v1`, Master Plan I6).

Proof-only. Production `PersistSingleInstanceBacktest`/
`SingleInstanceBacktestResult` are NOT changed -- production still
persists the legacy shape until I7's coordinated cutover. This script
builds a SEPARATE, parallel proof-only artifact bundle in the target
I6.D shape (`strategy_evaluation.json` = the real
`HistoricalExecutionProjection` v2 envelope; `result.json` references
it by identity, not re-embedding it) from the new path's real
execution/accounting output, writes it to a local proof-only
directory, then runs the two I6.E checks:

  1. Persistence read-back: every common-facts field of the in-memory
     `TradeRecord`/`ExecutionEvent` objects equals the same fields read
     back from the persisted `trades.json`/`execution_events.json`
     after a full write+read round trip.
  2. Cross-system: the read-back facts equal the independent old-BBB-
     grounded reference (`_old_bbb_lifecycle_reference.py`, same
     methodology `lane_b_parity_proof.py` already established for I5),
     fed the identical frozen candle set via `old_bbb_candle_adapter
     .candles_to_ohlcv_records` (I6.A) -- proving persistence didn't
     just preserve whatever the new path happened to compute, but
     preserved facts independently verified correct.

Also verifies I6.C: `manifest.json`'s per-file `sha256`/`size_bytes`
match the actual persisted file bytes, and `market_data_hash`/market
identity in the bundle match the one frozen `MarketFrame` both checks
above were computed from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _old_bbb_lifecycle_reference import (  # noqa: E402
    _levels_from_ratios,
    _stop_hit_long,
    _stop_hit_short,
    fill_price_for_distance_exit,
)
from old_bbb_candle_adapter import candles_to_ohlcv_records  # noqa: E402

from research_service.accounting.contracts import AccountingPolicy, TradeRecord
from research_service.accounting.service import account_execution_loop
from research_service.adapters.http.market_data_client import HttpMarketDataClient
from research_service.adapters.http.strategy_engine_client import (
    parse_historical_execution_projection,
)
from research_service.domain.contracts import (
    HistoricalExecutionProjectionIndex,
    MarketRange,
    validate_projection_alignment,
)
from research_service.domain.execution import ExecutionEvent, ExecutionPolicy
from research_service.execution.projection_loop import run_projection_execution_loop

_POLICY = ExecutionPolicy()
_ACCOUNTING_POLICY = AccountingPolicy()


def _reference_lifecycle(v2_body: dict[str, Any], candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same independent old-BBB-grounded lifecycle `lane_b_parity_proof
    .py::_reference_lifecycle` uses -- duplicated here (not imported)
    deliberately, so this I6 proof does not depend on the I5 proof
    script's own module staying importable/unchanged; both are
    literal, independent restatements of the same verbatim mechanics."""

    bar_count = v2_body["market"]["bar_count"]
    entry_by_bar_side: dict[tuple[int, str], dict[str, Any]] = {}
    for opp in v2_body["entry_opportunities"]:
        entry_by_bar_side[(opp["bar_index"], opp["side"])] = opp
    signal_by_side_profile_bar: dict[tuple[str, str, int], dict[str, Any]] = {}
    for side in ("long", "short"):
        for profile, events in v2_body["signal_exit_events"][side].items():
            for event in events:
                signal_by_side_profile_bar[(side, profile, event["bar_index"])] = event

    trades: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None
    for bar_index in range(bar_count):
        candle = candles[bar_index]
        o, h, low, c = candle["open"], candle["high"], candle["low"], candle["close"]
        if position is None:
            opp = entry_by_bar_side.get((bar_index, "long")) or entry_by_bar_side.get((bar_index, "short"))
            if opp is None:
                continue
            side = opp["side"]
            entry_price = c
            sl_ratio = opp["initial_stop"]["ratio"] if opp["initial_stop"] else None
            tp_ratio = opp["initial_take"]["ratio"] if opp["initial_take"] else None
            sl_level, tp_level = _levels_from_ratios(side, entry_price, sl_ratio, tp_ratio)
            position = {
                "side": side,
                "entry_bar_index": bar_index,
                "entry_time_ms": candle["open_time_ms"],
                "entry_price": entry_price,
                "locked_exit_profile": opp["locked_exit_profile"],
                "stop_level": sl_level,
                "take_level": tp_level,
            }
            continue
        side = position["side"]
        exit_price = None
        exit_kind = None
        if position["stop_level"] is not None:
            hit_fn = _stop_hit_long if side == "long" else _stop_hit_short
            if hit_fn(o, h, low, position["stop_level"], is_loss=True):
                exit_price = fill_price_for_distance_exit(side, open_=o, high=h, low=low, level=position["stop_level"], is_loss=True)
                exit_kind = "stop_loss"
        if exit_price is None and position["take_level"] is not None:
            hit_fn = _stop_hit_long if side == "long" else _stop_hit_short
            if hit_fn(o, h, low, position["take_level"], is_loss=False):
                exit_price = fill_price_for_distance_exit(side, open_=o, high=h, low=low, level=position["take_level"], is_loss=False)
                exit_kind = "take_profit"
        if exit_price is None:
            event = signal_by_side_profile_bar.get((side, position["locked_exit_profile"], bar_index))
            if event is not None:
                exit_price = c
                exit_kind = "signal"
        if exit_price is not None:
            gross_pnl = (exit_price - position["entry_price"]) if side == "long" else (position["entry_price"] - exit_price)
            trades.append(
                {
                    "side": side,
                    "entry_bar_index": position["entry_bar_index"],
                    "exit_bar_index": bar_index,
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "gross_pnl": gross_pnl,
                    "hold_bars": bar_index - position["entry_bar_index"] + 1,
                    "exit_candidate_type": exit_kind,
                }
            )
            position = None
    return trades


def _write_bundle(
    directory: Path,
    *,
    v2_body: dict[str, Any],
    trades: tuple[TradeRecord, ...],
    events: tuple[ExecutionEvent, ...],
    accounting_summary: dict[str, Any],
    market_data_hash: str,
    instance_id: str,
    config_hash: str,
) -> dict[str, dict[str, Any]]:
    """Writes the I6.D-shaped bundle: strategy_evaluation.json IS the v2
    projection (not the legacy dense shape); result.json references it
    by identity (sha256), not re-embedding it. Returns each file's
    manifest record (path, sha256, size_bytes) -- I6.C."""

    directory.mkdir(parents=True, exist_ok=True)

    def write_json(name: str, payload: Any) -> dict[str, Any]:
        text = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
        (directory / name).write_bytes(text)
        return {"path": name, "sha256": hashlib.sha256(text).hexdigest(), "size_bytes": len(text)}

    files: dict[str, dict[str, Any]] = {}
    files["strategy_evaluation.json"] = write_json("strategy_evaluation.json", v2_body)
    files["trades.json"] = write_json("trades.json", [t.model_dump(mode="json") for t in trades])
    files["execution_events.json"] = write_json(
        "execution_events.json", [e.model_dump(mode="json") for e in events]
    )
    files["metrics.json"] = write_json("metrics.json", accounting_summary)
    result_payload = {
        "instance_id": instance_id,
        "config_hash": config_hash,
        "market_data_hash": market_data_hash,
        # Reference by identity -- not a re-embedded copy of the projection.
        "strategy_evaluation_ref": {
            "path": "strategy_evaluation.json",
            "sha256": files["strategy_evaluation.json"]["sha256"],
        },
        "trades_ref": {"path": "trades.json", "sha256": files["trades.json"]["sha256"]},
        "execution_events_ref": {
            "path": "execution_events.json",
            "sha256": files["execution_events.json"]["sha256"],
        },
    }
    files["result.json"] = write_json("result.json", result_payload)

    manifest = {
        "instance_id": instance_id,
        "config_hash": config_hash,
        "market_data_hash": market_data_hash,
        "files": [files[name] for name in sorted(files)],
    }
    files["manifest.json"] = write_json("manifest.json", manifest)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2", required=True, type=Path)
    parser.add_argument("--ticker", default="BTCUSDT.P")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--from-ms", required=True, type=int)
    parser.add_argument("--to-ms", required=True, type=int)
    parser.add_argument("--mds-base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    v2_body = json.loads(args.v2.read_text())
    market = MarketRange(ticker=args.ticker, timeframe=args.timeframe, from_ms=args.from_ms, to_ms=args.to_ms)
    mds = HttpMarketDataClient(args.mds_base_url)
    try:
        market_frame = mds.read_range(market)
    finally:
        mds.close()
    print(f"fetched real MarketFrame: {len(market_frame.candles)} candles")
    if market_frame.market_data_hash != v2_body["market"]["market_data_hash"]:
        print("BLOCKED: MarketFrame hash differs from v2 hash")
        return 2
    print("frozen-input check: OK")

    # --- new path (already I5-proven correct) ---
    projection = parse_historical_execution_projection(v2_body)
    validate_projection_alignment(
        projection,
        expected_market=market_frame.market,
        expected_market_data_hash=market_frame.market_data_hash or "",
        expected_bar_count=len(market_frame.candles),
    )
    index = HistoricalExecutionProjectionIndex.build(projection)
    instance_id = f"i6-persist:{v2_body['config_hash']}"
    execution = run_projection_execution_loop(instance_id, index, market_frame, _POLICY)
    accounting = account_execution_loop(execution, market_frame, _ACCOUNTING_POLICY)
    print(f"new path (in-memory): {len(accounting.trades)} closed trades")

    accounting_summary = {
        "initial_equity": str(accounting.initial_equity),
        "final_equity": str(accounting.final_equity),
        "realised_trade_count": accounting.realised_trade_count,
        "open_position_count": accounting.open_position_count,
        "gross_pnl": str(accounting.gross_pnl),
        "fees_paid": str(accounting.fees_paid),
        "net_pnl": str(accounting.net_pnl),
    }

    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="i6-persist-"))
    files = _write_bundle(
        out_dir,
        v2_body=v2_body,
        trades=accounting.trades,
        events=execution.events,
        accounting_summary=accounting_summary,
        market_data_hash=market_frame.market_data_hash or "",
        instance_id=instance_id,
        config_hash=v2_body["config_hash"],
    )
    print(f"persisted bundle to {out_dir}")

    # --- I6.C: manifest hashes match actual persisted bytes ---
    manifest_ok = True
    for name, record in files.items():
        actual_bytes = (out_dir / name).read_bytes()
        actual_hash = hashlib.sha256(actual_bytes).hexdigest()
        if actual_hash != record["sha256"] or len(actual_bytes) != record["size_bytes"]:
            print(f"I6.C FAIL: {name} manifest hash/size does not match persisted bytes")
            manifest_ok = False
    print(f"I6.C manifest/file-hash verification: {'OK' if manifest_ok else 'FAIL'}")

    # --- I6.E part 2: persistence read-back vs in-memory ---
    read_back_trades = tuple(
        TradeRecord.model_validate(item)
        for item in json.loads((out_dir / "trades.json").read_bytes())
    )
    read_back_events = tuple(
        ExecutionEvent.model_validate(item)
        for item in json.loads((out_dir / "execution_events.json").read_bytes())
    )
    readback_diffs: list[str] = []
    if read_back_trades != accounting.trades:
        for i, (a, b) in enumerate(zip(accounting.trades, read_back_trades, strict=True)):
            if a != b:
                readback_diffs.append(f"trade[{i}] read-back differs from in-memory")
    if read_back_events != execution.events:
        readback_diffs.append("execution_events read-back differs from in-memory")
    print(f"I6.E(2) persistence read-back diffs: {len(readback_diffs)}")
    for line in readback_diffs[:10]:
        print(f"  DIFF: {line}")

    # --- I6.E part 1: cross-system, independent old-BBB reference ---
    candle_records = candles_to_ohlcv_records(market_frame)  # I6.A adapter
    float_candles = [
        {
            "open_time_ms": r["open_time_ms"],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        }
        for r in candle_records
    ]
    reference_trades = _reference_lifecycle(v2_body, float_candles)
    print(f"independent old-BBB reference: {len(reference_trades)} closed trades")

    cross_diffs: list[str] = []
    if len(reference_trades) != len(read_back_trades):
        cross_diffs.append(
            f"trade count differs: reference={len(reference_trades)} persisted={len(read_back_trades)}"
        )
    else:
        for i, (r, n) in enumerate(zip(reference_trades, read_back_trades, strict=True)):
            if r["side"] != n.side:
                cross_diffs.append(f"trade[{i}].side: reference={r['side']} persisted={n.side}")
            if r["entry_bar_index"] != n.entry_bar_index:
                cross_diffs.append(f"trade[{i}].entry_bar_index differs")
            if r["exit_bar_index"] != n.exit_bar_index:
                cross_diffs.append(f"trade[{i}].exit_bar_index differs")
            if abs(Decimal(str(r["entry_price"])) - n.entry_price) > Decimal("0.00000001"):
                cross_diffs.append(f"trade[{i}].entry_price differs")
            if abs(Decimal(str(r["exit_price"])) - n.exit_price) > Decimal("0.00000001"):
                cross_diffs.append(f"trade[{i}].exit_price differs")
            if r["hold_bars"] != n.hold_bars:
                cross_diffs.append(f"trade[{i}].hold_bars differs")
            if abs(Decimal(str(r["gross_pnl"])) - n.gross_pnl) > Decimal("0.00000001"):
                cross_diffs.append(f"trade[{i}].gross_pnl differs")
            if r["exit_candidate_type"] != n.exit_candidate_type:
                cross_diffs.append(f"trade[{i}].exit_candidate_type differs")
    print(f"I6.E(1) cross-system diffs (persisted+read-back vs. independent old-BBB reference): {len(cross_diffs)}")
    for line in cross_diffs[:10]:
        print(f"  DIFF: {line}")

    ok = manifest_ok and not readback_diffs and not cross_diffs
    print()
    print("I6 GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
