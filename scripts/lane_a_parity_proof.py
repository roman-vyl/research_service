"""I5 Lane A parity proof (`compact-strategy-evaluation-boundary-v1`,
Master Plan I5.B).

Proof-only, not production-wired. Reads the two JSON files produced by
`strategy_engine/scripts/serialize_lane_a_dual_reference.py` (the
legacy dense `StrategyRangeResult` envelope and the new
`strategy_evaluation_execution.v2` envelope, both resolved from the
same explicit market range), fetches ONE real `MarketFrame` for that
same range, and runs:

  - Lane A reference: `run_unified_execution_loop` (legacy, unmodified)
    fed by a `StrategyEvaluationResult` built proof-only from the dense
    envelope -- never through Engine's live `/range` route or
    `evaluate_range`'s HTTP client (per `research-historical-execution-
    parity-v1`'s corrected "Lane A reference"/"Known intermediate
    incompatibility" requirements).
  - New path: `parse_historical_execution_projection` ->
    `validate_projection_alignment` -> `HistoricalExecutionProjectionIndex
    .build` -> `run_projection_execution_loop` (I4).

Both execution results go through the same, unmodified
`account_execution_loop`. Reports a field-by-field diff over EVERY
`TradeRecord` field both sides actually produce (excluding only the
self-referential trade_id/position_id/instance_id labels) plus every
`TradePathMetrics` field, plus every `TradeAccountingResult` field --
this is Lane A's own real comparison surface, per `research-
historical-execution-parity-v1`'s per-lane scoping: `exit_rule_id`/
`exit_component_id`/`exit_kind` are reported separately and NOT folded
into the pass/fail count, since Lane A's reference path structurally
never populates them (a known, already-reported architectural fact,
not a defect discovered here) -- `exit_layer` IS compared normally,
since both sides already agree on the canonical `"exit_policy"`
constant regardless of that gap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from research_service.accounting.contracts import AccountingPolicy, TradePathMetrics, TradeRecord
from research_service.accounting.service import account_execution_loop
from research_service.adapters.http.market_data_client import HttpMarketDataClient
from research_service.adapters.http.strategy_engine_client import (
    parse_historical_execution_projection,
)
from research_service.domain.contracts import (
    HistoricalExecutionProjectionIndex,
    MarketRange,
    StrategyEvaluationResult,
    validate_projection_alignment,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.loop import run_unified_execution_loop
from research_service.execution.projection_loop import run_projection_execution_loop

_POLICY = ExecutionPolicy()
_ACCOUNTING_POLICY = AccountingPolicy()


def _build_legacy_evaluation(body: dict[str, Any], *, instance_id: str) -> StrategyEvaluationResult:
    """Mirrors `strategy_engine_client.py::_parse_evaluation_result`
    exactly, reading from a proof-only file instead of an HTTP response
    -- see module docstring for why this bypasses the live route/client."""

    market = body["market"]
    features = body["features"]
    entries = {
        str(side): tuple(bool(v) for v in values)
        for side, values in body["entries"].items()
        if isinstance(values, list)
    }
    parsed_market = MarketRange(
        ticker=str(market.get("ticker", "")),
        timeframe=str(market.get("base_timeframe", "")),
        from_ms=int(market.get("from_ms", -1)),
        to_ms=int(market.get("to_ms", -1)),
    )
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id=str(body.get("strategy_id", "")),
        instance_id=instance_id,
        config_hash=str(body.get("config_hash", "")),
        market=parsed_market,
        bar_count=len(features["time_ms"]),
        market_data_hash=str(features.get("market_data_hash", "")),
        time_ms=tuple(int(v) for v in features["time_ms"]),
        entries=entries,
        exit_policy=body["exit_policy"],
        component_evidence=body.get("component_evidence", {}),
        raw=body,
    )


_ENTRY_FIELDS = ("bar_index", "side", "time_ms", "reference_price", "fill_price")
# Every TradeRecord field both Lane A sides actually produce (both run
# through the same, unmodified account_execution_loop) -- excludes only
# self-referential IDs (trade_id/position_id/instance_id, which are
# Research-generated labels, not cross-system content) and the
# attribution fields (exit_rule_id/exit_component_id/exit_kind --
# reported separately below, since the legacy reference structurally
# never populates them; exit_layer IS compared here since both sides
# already agree it's the canonical "exit_policy" constant).
_TRADE_FIELDS = (
    "side",
    "entry_bar_index",
    "exit_bar_index",
    "entry_time_ms",
    "exit_time_ms",
    "entry_price",
    "exit_price",
    "quantity",
    "entry_notional",
    "exit_notional",
    "gross_pnl",
    "entry_fee",
    "exit_fee",
    "fees_paid",
    "net_pnl",
    "gross_return_pct",
    "net_return_pct",
    "equity_before",
    "equity_after",
    "hold_bars",
    "hold_ms",
    "exit_candidate_type",
    "exit_reason",
    "exit_layer",
)
_PATH_FIELDS = (
    "mfe_price",
    "mfe_pct",
    "mfe_bar_index",
    "mfe_bars_from_entry",
    "mae_price",
    "mae_pct",
    "mae_bar_index",
    "mae_bars_from_entry",
    "captured_price",
    "captured_pct",
    "capture_ratio",
    "giveback_price",
    "giveback_pct",
    "bars_from_mfe_to_exit",
)
_ATTRIBUTION_FIELDS = ("exit_rule_id", "exit_component_id", "exit_kind")


def _diff_path(i: int, r: TradePathMetrics, n: TradePathMetrics) -> list[str]:
    diffs: list[str] = []
    for field in _PATH_FIELDS:
        rv, nv = getattr(r, field), getattr(n, field)
        if rv != nv:
            diffs.append(f"trade[{i}].path.{field}: reference={rv!r} new={nv!r}")
    return diffs


def _diff_trades(reference: tuple[TradeRecord, ...], new: tuple[TradeRecord, ...]) -> list[str]:
    diffs: list[str] = []
    if len(reference) != len(new):
        diffs.append(f"trade count differs: reference={len(reference)} new={len(new)}")
        return diffs
    for i, (r, n) in enumerate(zip(reference, new, strict=True)):
        for field in _TRADE_FIELDS:
            rv, nv = getattr(r, field), getattr(n, field)
            if rv != nv:
                diffs.append(f"trade[{i}].{field}: reference={rv!r} new={nv!r}")
        diffs.extend(_diff_path(i, r.path, n.path))
    return diffs


def _attribution_report(reference: tuple[TradeRecord, ...], new: tuple[TradeRecord, ...]) -> list[str]:
    lines: list[str] = []
    for i, (r, n) in enumerate(zip(reference, new, strict=True)):
        r_attr = tuple(getattr(r, f) for f in _ATTRIBUTION_FIELDS)
        n_attr = tuple(getattr(n, f) for f in _ATTRIBUTION_FIELDS)
        if r_attr != n_attr:
            lines.append(f"trade[{i}]: reference={r_attr} new={n_attr}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dense", required=True, type=Path)
    parser.add_argument("--v2", required=True, type=Path)
    parser.add_argument("--ticker", default="BTCUSDT.P")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--from-ms", required=True, type=int)
    parser.add_argument("--to-ms", required=True, type=int)
    parser.add_argument("--mds-base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)

    dense_body = json.loads(args.dense.read_text())
    v2_body = json.loads(args.v2.read_text())

    # Both envelopes must be the same strategy identity -- config_hash is
    # Engine's own hash over {strategy_id, raw_spec}, present on both.
    if dense_body["config_hash"] != v2_body["config_hash"]:
        print("BLOCKED: dense and v2 config_hash differ -- not the same strategy identity")
        return 2

    # instance_id is Research-owned and Engine never echoes it -- any fixed,
    # deterministic string works for this proof; both execution loops just
    # need it to agree with itself for internal consistency checks.
    instance_id = f"i5-lane-a:{dense_body['config_hash']}"

    market = MarketRange(
        ticker=args.ticker, timeframe=args.timeframe, from_ms=args.from_ms, to_ms=args.to_ms
    )
    market_data_client = HttpMarketDataClient(args.mds_base_url)
    try:
        market_frame = market_data_client.read_range(market)
    finally:
        market_data_client.close()
    print(
        f"fetched real MarketFrame: {len(market_frame.candles)} candles, "
        f"market_data_hash={market_frame.market_data_hash}"
    )
    if market_frame.market_data_hash != dense_body["features"]["market_data_hash"]:
        print("BLOCKED: Research's own MarketFrame hash differs from Engine's dense-path hash")
        return 2
    if market_frame.market_data_hash != v2_body["market"]["market_data_hash"]:
        print("BLOCKED: Research's own MarketFrame hash differs from Engine's v2-path hash")
        return 2
    print("frozen-input check (Research side): OK -- all three hashes agree")

    # --- Lane A reference: legacy path ---
    legacy_evaluation = _build_legacy_evaluation(dense_body, instance_id=instance_id)
    legacy_execution = run_unified_execution_loop(legacy_evaluation, market_frame, _POLICY)
    legacy_accounting = account_execution_loop(legacy_execution, market_frame, _ACCOUNTING_POLICY)
    print(f"legacy reference: {len(legacy_accounting.trades)} closed trade(s)")

    # --- New path ---
    projection = parse_historical_execution_projection(v2_body)
    validate_projection_alignment(
        projection,
        expected_market=market_frame.market,
        expected_market_data_hash=market_frame.market_data_hash or "",
        expected_bar_count=len(market_frame.candles),
    )
    index = HistoricalExecutionProjectionIndex.build(projection)
    new_execution = run_projection_execution_loop(instance_id, index, market_frame, _POLICY)
    new_accounting = account_execution_loop(new_execution, market_frame, _ACCOUNTING_POLICY)
    print(f"new path: {len(new_accounting.trades)} closed trade(s)")

    diffs = _diff_trades(legacy_accounting.trades, new_accounting.trades)
    attribution_lines = (
        _attribution_report(legacy_accounting.trades, new_accounting.trades)
        if len(legacy_accounting.trades) == len(new_accounting.trades)
        else []
    )

    print()
    print(f"=== Lane A common-facts diff: {len(diffs)} ===")
    for line in diffs[:50]:
        print(f"  DIFF: {line}")
    if len(diffs) > 50:
        print(f"  ... and {len(diffs) - 50} more")

    print()
    print(f"=== Lane A attribution report (informational, not pass/fail): {len(attribution_lines)} trades differ ===")
    for line in attribution_lines[:5]:
        print(f"  {line}")
    if len(attribution_lines) > 5:
        print(f"  ... and {len(attribution_lines) - 5} more")

    print()
    print(
        f"accounting: legacy realised={legacy_accounting.realised_trade_count} "
        f"gross_pnl={legacy_accounting.gross_pnl} net_pnl={legacy_accounting.net_pnl} | "
        f"new realised={new_accounting.realised_trade_count} "
        f"gross_pnl={new_accounting.gross_pnl} net_pnl={new_accounting.net_pnl}"
    )
    accounting_diffs = []
    for field in (
        "initial_equity",
        "realised_trade_count",
        "open_position_count",
        "gross_pnl",
        "fees_paid",
        "net_pnl",
        "final_equity",
    ):
        rv, nv = getattr(legacy_accounting, field), getattr(new_accounting, field)
        if rv != nv:
            accounting_diffs.append(f"{field}: reference={rv!r} new={nv!r}")
    if accounting_diffs:
        print("ACCOUNTING DIFFS:")
        for line in accounting_diffs:
            print(f"  DIFF: {line}")

    return 0 if not diffs and not accounting_diffs else 1


if __name__ == "__main__":
    sys.exit(main())
