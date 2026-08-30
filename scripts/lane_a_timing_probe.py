"""Controlled timing probe (not a correctness proof) -- slices the
already-serialized full_available dense/v2 envelopes to N bars, builds
a synthetic MarketFrame of matching length, and times the legacy vs.
new execution+accounting stages separately at a few sizes, to
extrapolate full-scale (676k-bar) wall time without re-running the
full thing blind.
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from research_service.accounting.contracts import AccountingPolicy
from research_service.accounting.service import account_execution_loop
from research_service.adapters.http.strategy_engine_client import (
    parse_historical_execution_projection,
)
from research_service.domain.contracts import (
    Candle,
    HistoricalExecutionProjectionIndex,
    MarketFrame,
    MarketRange,
    StrategyEvaluationResult,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.loop import run_unified_execution_loop
from research_service.execution.projection_loop import run_projection_execution_loop

_POLICY = ExecutionPolicy()
_ACCOUNTING = AccountingPolicy()


def _slice_dense(body: dict[str, Any], n: int) -> dict[str, Any]:
    market = dict(body["market"])
    market["to_ms"] = market["from_ms"] + n * 300_000
    market["bar_count"] = n
    features = dict(body["features"])
    features["time_ms"] = features["time_ms"][:n]
    features["market_data_hash"] = f"synthetic-{n}"
    entries = {side: values[:n] for side, values in body["entries"].items()}

    def slice_ep(ep: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in ep.items():
            if isinstance(v, dict):
                out[k] = {
                    side: values[:n] if isinstance(values, list) else values
                    for side, values in v.items()
                }
            elif isinstance(v, list) and len(v) == len(body["entries"]["long"]):
                out[k] = v[:n]
            else:
                out[k] = v
        return out

    return {
        **body,
        "market": market,
        "features": features,
        "entries": entries,
        "exit_policy": slice_ep(body["exit_policy"]),
    }


def _slice_v2(body: dict[str, Any], n: int) -> dict[str, Any]:
    market = dict(body["market"])
    market["to_ms"] = market["from_ms"] + n * 300_000
    market["bar_count"] = n
    market["market_data_hash"] = f"synthetic-{n}"
    entry_opportunities = [o for o in body["entry_opportunities"] if o["bar_index"] < n]

    def slice_events(events_by_profile: dict[str, Any]) -> dict[str, Any]:
        return {
            profile: [e for e in events if e["bar_index"] < n]
            for profile, events in events_by_profile.items()
        }

    return {
        **body,
        "market": market,
        "entry_opportunities": entry_opportunities,
        "signal_exit_events": {
            "long": slice_events(body["signal_exit_events"]["long"]),
            "short": slice_events(body["signal_exit_events"]["short"]),
        },
    }


def _synthetic_frame(n: int, market: MarketRange, hash_: str) -> MarketFrame:
    candles = tuple(
        Candle(
            open_time_ms=market.from_ms + i * 300_000,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for i in range(n)
    )
    return MarketFrame(market=market, candles=candles, market_data_hash=hash_)


def main() -> int:
    dense_path = Path(sys.argv[1])
    v2_path = Path(sys.argv[2])
    sizes = [int(x) for x in sys.argv[3:]] or [5_000, 20_000, 50_000]

    dense_full = json.loads(dense_path.read_text())
    v2_full = json.loads(v2_path.read_text())

    for n in sizes:
        dense = _slice_dense(dense_full, n)
        v2 = _slice_v2(v2_full, n)
        market_range = MarketRange(
            ticker=v2["market"]["ticker"],
            timeframe=v2["market"]["base_timeframe"],
            from_ms=v2["market"]["from_ms"],
            to_ms=v2["market"]["to_ms"],
        )
        frame = _synthetic_frame(n, market_range, f"synthetic-{n}")

        legacy_eval = StrategyEvaluationResult(
            contract_version="strategy_evaluation.v1",
            strategy_id=dense["strategy_id"],
            instance_id="timing-probe",
            config_hash=dense["config_hash"],
            market=market_range,
            bar_count=n,
            market_data_hash=f"synthetic-{n}",
            time_ms=tuple(dense["features"]["time_ms"]),
            entries={s: tuple(bool(x) for x in v) for s, v in dense["entries"].items()},
            exit_policy=dense["exit_policy"],
            component_evidence={},
            raw={},
        )

        t0 = time.perf_counter()
        legacy_execution = run_unified_execution_loop(legacy_eval, frame, _POLICY)
        t1 = time.perf_counter()
        legacy_accounting = account_execution_loop(legacy_execution, frame, _ACCOUNTING)
        t2 = time.perf_counter()

        projection = parse_historical_execution_projection(v2)
        index = HistoricalExecutionProjectionIndex.build(projection)
        t3 = time.perf_counter()
        new_execution = run_projection_execution_loop("timing-probe", index, frame, _POLICY)
        t4 = time.perf_counter()
        new_accounting = account_execution_loop(new_execution, frame, _ACCOUNTING)
        t5 = time.perf_counter()

        print(
            f"n={n:>7} "
            f"legacy_loop={t1-t0:7.3f}s legacy_acct={t2-t1:6.3f}s "
            f"decode+index={t3-t2:6.3f}s new_loop={t4-t3:7.3f}s new_acct={t5-t4:6.3f}s "
            f"total={t5-t0:8.3f}s "
            f"legacy_trades={len(legacy_accounting.trades)} new_trades={len(new_accounting.trades)}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
