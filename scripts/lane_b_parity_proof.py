"""I5 Lane B parity proof (`compact-strategy-evaluation-boundary-v1`,
Master Plan I5.C).

Proof-only. Runs the real new path (real v2 envelope -> real strict
parser/alignment/index -> `run_projection_execution_loop` -> real
`account_execution_loop`) against an INDEPENDENT old-BBB-grounded trade-
lifecycle reference (`_old_bbb_lifecycle_reference.py`, verbatim OHLC-
gap/fill mechanics from `roman-vyl/_bbb_new_gen@cddc836`), on the real
profile-sensitive production-like adversarial spec, over a real MDS
window.

The independent reference uses the real v2 projection's
`entry_opportunities`/`signal_exit_events` as INPUT DATA (already
proven correct at `strategy_engine`'s I2 -- not re-litigated here), and
independently reimplements the EXECUTION lifecycle on top of that data
(locked-profile capture, protection-level resolution, OHLC exit-hit
detection/fill price, same-bar priority stop<take<signal, accounting)
from scratch -- it never calls `execution/projection_loop.py`,
`execution/projection_entry.py`, `execution/projection_static_exits.py`,
or Research's legacy execution path.

Also runs the mandatory negative control: for every closed reference
trade, recomputes what a DELIBERATELY WRONG current-bar-profile signal
lookup (using Engine's native `profile_long`/`profile_short` proof-only
timeline, never the locked profile) would have selected, and reports
where it diverges from the correct locked-profile result -- proving the
scenario actually distinguishes the two interpretations.

Comparison surface (mandatory, exact): side, entry/exit bar_index,
entry/exit price, hold_bars, gross_pnl/net_pnl (comparable to the
new side's TradeRecord.gross_pnl/.net_pnl only because
_ACCOUNTING_POLICY is asserted zero-fee below -- the independent
reference has no fee model), exit_candidate_type, locked_exit_profile,
and exit attribution (exit_rule_id/exit_component_id/exit_kind/
exit_layer).

Deliberately NOT compared for Lane B: entry_notional/exit_notional/
entry_fee/exit_fee/equity_before/equity_after (accounting bookkeeping
the independent reference never computes -- these are proven, on real
full-scale data, by Lane A instead; `research-historical-execution-
parity-v1`'s own "Accounting parity is a consequence, not a separate
computation" requirement is why re-deriving them independently here
would not add evidence) and `TradePathMetrics` (mfe/mae/captured/
giveback -- the independent reference does not scan intrabar OHLC for
these; nothing in this proof claims they were checked). This is an
explicit scope boundary, not an oversight -- see `research-
historical-execution-parity-v1`'s per-lane "Zero-diff comparison
surface" split.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from _old_bbb_lifecycle_reference import (
    _levels_from_ratios,
    _stop_hit_long,
    _stop_hit_short,
    fill_price_for_distance_exit,
)

from research_service.accounting.contracts import AccountingPolicy
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
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.projection_loop import run_projection_execution_loop

sys.path.insert(0, str(Path(__file__).resolve().parent))

_POLICY = ExecutionPolicy()
_ACCOUNTING_POLICY = AccountingPolicy()


def _reference_lifecycle(
    v2_body: dict[str, Any],
    candles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Independent old-BBB-grounded trade lifecycle over the real v2
    projection's entry_opportunities/signal_exit_events (input data) and
    real OHLC (input data), using verbatim old-BBB fill mechanics."""

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
            opp = entry_by_bar_side.get((bar_index, "long")) or entry_by_bar_side.get(
                (bar_index, "short")
            )
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
                "stop_attribution": opp["initial_stop"]["attribution"] if opp["initial_stop"] else None,
                "take_attribution": opp["initial_take"]["attribution"] if opp["initial_take"] else None,
            }
            continue

        side = position["side"]
        exit_price = None
        exit_kind = None
        attribution = None
        if position["stop_level"] is not None:
            hit_fn = _stop_hit_long if side == "long" else _stop_hit_short
            if hit_fn(o, h, low, position["stop_level"], is_loss=True):
                exit_price = fill_price_for_distance_exit(
                    side, open_=o, high=h, low=low, level=position["stop_level"], is_loss=True
                )
                exit_kind = "stop_loss"
                attribution = position["stop_attribution"]
        if exit_price is None and position["take_level"] is not None:
            hit_fn = _stop_hit_long if side == "long" else _stop_hit_short
            if hit_fn(o, h, low, position["take_level"], is_loss=False):
                exit_price = fill_price_for_distance_exit(
                    side, open_=o, high=h, low=low, level=position["take_level"], is_loss=False
                )
                exit_kind = "take_profit"
                attribution = position["take_attribution"]
        if exit_price is None:
            event = signal_by_side_profile_bar.get((side, position["locked_exit_profile"], bar_index))
            if event is not None:
                exit_price = c
                exit_kind = "signal"
                attribution = event["candidates"][0]["attribution"]

        if exit_price is not None:
            gross_pnl = (
                (exit_price - position["entry_price"])
                if side == "long"
                else (position["entry_price"] - exit_price)
            )
            trades.append(
                {
                    "side": side,
                    "entry_bar_index": position["entry_bar_index"],
                    "exit_bar_index": bar_index,
                    "entry_time_ms": position["entry_time_ms"],
                    "exit_time_ms": candle["open_time_ms"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "gross_pnl": gross_pnl,
                    "hold_bars": bar_index - position["entry_bar_index"] + 1,
                    "exit_candidate_type": exit_kind,
                    "locked_exit_profile": position["locked_exit_profile"],
                    "exit_rule_id": attribution["rule_id"] if attribution else None,
                    "exit_component_id": attribution["component_id"] if attribution else None,
                    "exit_kind": attribution["exit_kind"] if attribution else None,
                }
            )
            position = None

    return trades


def _negative_control(
    reference_trades: list[dict[str, Any]],
    v2_body: dict[str, Any],
    profile_timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """For each reference trade closed by a signal exit, recompute what a
    WRONG current-bar-profile lookup would have selected instead of the
    locked profile, and report where it diverges."""

    signal_by_side_profile_bar: dict[tuple[str, str, int], dict[str, Any]] = {}
    for side in ("long", "short"):
        for profile, events in v2_body["signal_exit_events"][side].items():
            for event in events:
                signal_by_side_profile_bar[(side, profile, event["bar_index"])] = event

    divergences: list[dict[str, Any]] = []
    for trade in reference_trades:
        side = trade["side"]
        locked_profile = trade["locked_exit_profile"]
        current_profile_series = profile_timeline[f"profile_{side}"]
        # Scan forward from entry+1 for what the WRONG current-profile
        # interpretation would have picked as its first firing bar.
        wrong_exit_bar = None
        wrong_rule_id = None
        for bar_index in range(trade["entry_bar_index"] + 1, trade["exit_bar_index"] + 1):
            current_profile = current_profile_series[bar_index]
            event = signal_by_side_profile_bar.get((side, current_profile, bar_index))
            if event is not None:
                wrong_exit_bar = bar_index
                wrong_rule_id = event["candidates"][0]["attribution"]["rule_id"]
                break
        if trade["exit_candidate_type"] != "signal":
            continue
        correct = (trade["exit_bar_index"], trade["exit_rule_id"])
        wrong = (wrong_exit_bar, wrong_rule_id)
        if correct != wrong:
            divergences.append(
                {
                    "entry_bar_index": trade["entry_bar_index"],
                    "locked_profile": locked_profile,
                    "correct_locked_profile_result": correct,
                    "wrong_current_profile_result": wrong,
                }
            )
    return divergences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2", required=True, type=Path)
    parser.add_argument("--profile-timeline", required=True, type=Path)
    parser.add_argument("--ticker", default="BTCUSDT.P")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--from-ms", required=True, type=int)
    parser.add_argument("--to-ms", required=True, type=int)
    parser.add_argument("--mds-base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)

    v2_body = json.loads(args.v2.read_text())
    profile_timeline = json.loads(args.profile_timeline.read_text())

    market = MarketRange(
        ticker=args.ticker, timeframe=args.timeframe, from_ms=args.from_ms, to_ms=args.to_ms
    )
    market_data_client = HttpMarketDataClient(args.mds_base_url)
    try:
        market_frame = market_data_client.read_range(market)
    finally:
        market_data_client.close()
    print(f"fetched real MarketFrame: {len(market_frame.candles)} candles")

    if market_frame.market_data_hash != v2_body["market"]["market_data_hash"]:
        print("BLOCKED: Research's MarketFrame hash differs from Engine's v2 hash")
        return 2
    if market_frame.market_data_hash != profile_timeline["market_data_hash"]:
        print("BLOCKED: Research's MarketFrame hash differs from the profile-timeline hash")
        return 2
    print("frozen-input check: OK -- all three hashes agree")

    candles = [
        {
            "open_time_ms": c.open_time_ms,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
        }
        for c in market_frame.candles
    ]

    print("=== independent old-BBB lifecycle reference ===")
    reference_trades = _reference_lifecycle(v2_body, candles)
    print(f"reference: {len(reference_trades)} closed trade(s)")

    print("=== new path (real pipeline) ===")
    projection = parse_historical_execution_projection(v2_body)
    validate_projection_alignment(
        projection,
        expected_market=market_frame.market,
        expected_market_data_hash=market_frame.market_data_hash or "",
        expected_bar_count=len(market_frame.candles),
    )
    index = HistoricalExecutionProjectionIndex.build(projection)
    instance_id = f"i5-lane-b:{v2_body['config_hash']}"
    new_execution = run_projection_execution_loop(instance_id, index, market_frame, _POLICY)
    new_accounting = account_execution_loop(new_execution, market_frame, _ACCOUNTING_POLICY)
    print(f"new path: {len(new_accounting.trades)} closed trade(s)")
    new_closed_positions = [p for p in new_execution.positions if p.status == "closed"]

    print()
    print(f"=== Lane B diff: {len(reference_trades)} reference vs {len(new_accounting.trades)} new ===")
    diffs: list[str] = []
    if len(reference_trades) != len(new_accounting.trades):
        diffs.append(f"trade count differs: reference={len(reference_trades)} new={len(new_accounting.trades)}")
    else:
        for i, (r, n, np) in enumerate(
            zip(reference_trades, new_accounting.trades, new_closed_positions, strict=True)
        ):
            if r["locked_exit_profile"] != np.position.locked_exit_profile:
                diffs.append(
                    f"trade[{i}].locked_exit_profile: reference={r['locked_exit_profile']} "
                    f"new={np.position.locked_exit_profile}"
                )
            if r["side"] != n.side:
                diffs.append(f"trade[{i}].side: reference={r['side']} new={n.side}")
            if r["entry_bar_index"] != n.entry_bar_index:
                diffs.append(f"trade[{i}].entry_bar_index: reference={r['entry_bar_index']} new={n.entry_bar_index}")
            if r["exit_bar_index"] != n.exit_bar_index:
                diffs.append(f"trade[{i}].exit_bar_index: reference={r['exit_bar_index']} new={n.exit_bar_index}")
            if abs(Decimal(str(r["entry_price"])) - n.entry_price) > Decimal("0.00000001"):
                diffs.append(f"trade[{i}].entry_price: reference={r['entry_price']} new={n.entry_price}")
            if abs(Decimal(str(r["exit_price"])) - n.exit_price) > Decimal("0.00000001"):
                diffs.append(f"trade[{i}].exit_price: reference={r['exit_price']} new={n.exit_price}")
            if r["hold_bars"] != n.hold_bars:
                diffs.append(f"trade[{i}].hold_bars: reference={r['hold_bars']} new={n.hold_bars}")
            # gross_pnl/net_pnl: the independent reference computes a pure
            # price-difference gross_pnl with no fee model. Comparable to
            # both n.gross_pnl and n.net_pnl only because _ACCOUNTING_POLICY
            # uses the zero-fee default (entry_fee_rate=exit_fee_rate=0), so
            # gross_pnl == net_pnl on the new side too -- asserted explicitly
            # below rather than assumed.
            if _ACCOUNTING_POLICY.entry_fee_rate != 0 or _ACCOUNTING_POLICY.exit_fee_rate != 0:
                raise AssertionError(
                    "Lane B's independent reference has no fee model -- "
                    "_ACCOUNTING_POLICY must stay zero-fee for gross_pnl/net_pnl to be comparable"
                )
            if abs(Decimal(str(r["gross_pnl"])) - n.gross_pnl) > Decimal("0.00000001"):
                diffs.append(f"trade[{i}].gross_pnl: reference={r['gross_pnl']} new={n.gross_pnl}")
            if n.gross_pnl != n.net_pnl:
                diffs.append(f"trade[{i}].net_pnl: expected == gross_pnl under zero fees, got {n.net_pnl}")
            if r["exit_candidate_type"] != n.exit_candidate_type:
                diffs.append(f"trade[{i}].exit_candidate_type: reference={r['exit_candidate_type']} new={n.exit_candidate_type}")
            if r["exit_rule_id"] != n.exit_rule_id:
                diffs.append(f"trade[{i}].exit_rule_id: reference={r['exit_rule_id']} new={n.exit_rule_id}")
            if r["exit_component_id"] != n.exit_component_id:
                diffs.append(f"trade[{i}].exit_component_id: reference={r['exit_component_id']} new={n.exit_component_id}")
            if r["exit_kind"] != n.exit_kind:
                diffs.append(f"trade[{i}].exit_kind: reference={r['exit_kind']} new={n.exit_kind}")
            if n.exit_layer != "exit_policy":
                diffs.append(f"trade[{i}].exit_layer: new={n.exit_layer} (expected exit_policy)")
    for line in diffs[:80]:
        print(f"  DIFF: {line}")
    if len(diffs) > 80:
        print(f"  ... and {len(diffs) - 80} more")

    print()
    print("=== negative control: locked vs. current-profile divergence ===")
    negative_control = _negative_control(reference_trades, v2_body, profile_timeline)
    print(f"trades where locked-profile result differs from wrong current-profile result: {len(negative_control)}")
    for item in negative_control[:5]:
        print(f"  {item}")

    return 0 if not diffs and negative_control else 1


if __name__ == "__main__":
    sys.exit(main())
