"""I5 proof-only decode of a real Strategy Engine v2 envelope
(`compact-strategy-evaluation-boundary-v1`, Master Plan checkpoint I5,
task I5.A).

NOT `src/`, not wired into any production request path. Reads the JSON
file produced by `strategy_engine/scripts/i5_serialize_projection_v2.py`
and decodes it through Research's actual, already-shipped strict
parser/alignment/index (I3) -- exercising the "v2 envelope decodes
through the real Research parser unmodified" scenario
(`research-historical-execution-parity-v1`) without any production
route change.

Usage:
    python scripts/i5_decode_projection.py \
        --projection projection_v2.json \
        --expected-ticker BTCUSDT.P --expected-timeframe 5m \
        --expected-from-ms 0 --expected-to-ms 300000

Exits non-zero (and prints the raised error) on any decode or
alignment failure -- this script proves parse-and-align succeeds, it
does not swallow failures.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection", required=True, type=Path)
    parser.add_argument("--expected-ticker", required=True)
    parser.add_argument("--expected-timeframe", required=True)
    parser.add_argument("--expected-from-ms", required=True, type=int)
    parser.add_argument("--expected-to-ms", required=True, type=int)
    parser.add_argument("--mds-base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--drive-loop",
        action="store_true",
        help="Also fetch real candles and drive run_projection_execution_loop (I5.A gate)",
    )
    args = parser.parse_args(argv)

    body = json.loads(args.projection.read_text())
    projection = parse_historical_execution_projection(body)

    expected_market = MarketRange(
        ticker=args.expected_ticker,
        timeframe=args.expected_timeframe,
        from_ms=args.expected_from_ms,
        to_ms=args.expected_to_ms,
    )
    validate_projection_alignment(
        projection,
        expected_market=expected_market,
        expected_market_data_hash=projection.market_data_hash,
        expected_bar_count=projection.bar_count,
    )

    index = HistoricalExecutionProjectionIndex.build(projection)

    print(f"contract_version: {projection.contract_version}")
    print(f"strategy_id: {projection.strategy_id}")
    print(f"market: {projection.market}")
    print(f"bar_count: {projection.bar_count}")
    print(f"market_data_hash: {projection.market_data_hash}")
    print(f"entry_opportunities: {len(projection.entry_opportunities)}")
    for side in ("long", "short"):
        for profile in ("aligned", "countertrend", "neutral"):
            events = getattr(projection.signal_exit_events, side)[profile]
            if events:
                print(f"signal_exit_events[{side}][{profile}]: {len(events)} events")
    print(f"index built: entry lookups + signal lookups ready (id={id(index)})")
    print("decode + alignment: OK")

    if args.drive_loop:
        market_data_client = HttpMarketDataClient(args.mds_base_url)
        try:
            market_frame = market_data_client.read_range(expected_market)
        finally:
            market_data_client.close()
        result = run_projection_execution_loop(
            projection.strategy_id, index, market_frame, ExecutionPolicy()
        )
        print(
            f"run_projection_execution_loop: OK -- "
            f"{len(result.positions)} closed position(s), "
            f"final_open_position={'yes' if result.final_open_position else 'no'}, "
            f"{len(result.events)} event(s)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
