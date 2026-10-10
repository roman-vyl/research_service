## 1. Measure before apply

- [ ] 1.1 Memory breakdown of the current `MarketFrame` for the full BTCUSDT.P window.
- [ ] 1.2 MDS price format (numbers vs strings), fractional digits and magnitude, BTCUSDT.P and ETHUSDT.P.
- [ ] 1.3 Baseline for two reference runs: peak RSS, wall time, trade artifacts. Run A: `ratio_4d` fixed SL/TP.
      Run B: `trailing_geometry_fee4_4d` (managed trailing).

## 2. Implementation (after the owner approves the OpenSpec)

- [ ] 2.1 Columnar `MarketFrame` with the `Sequence[Candle]` view; grid check on the time array.
- [ ] 2.2 Direct decoder in `market_data_client.py`; fail loudly on int64 overflow.
- [ ] 2.3 Tests: exact `Decimal` round trip (value and exponent, including trailing zeros), sequence behaviour
      (negative index, slice, empty, iteration), construction from a tuple of `Candle`.

## 3. Acceptance

- [ ] 3.1 Exact parity on Run A and Run B, old code against new code: same entry/exit bars, sides, exit reasons,
      entry/SL/TP/exit prices, number of trades, managed event sequence, fees and accounting; trade and metrics
      artifacts byte-identical after deterministic serialization. No tolerance on trading results.
- [ ] 3.2 Existing test suite, ruff, mypy green.
- [ ] 3.3 Peak RSS and wall time before and after reported to the owner; a wall-time regression is reported
      before merge.
- [ ] 3.4 Owner manual check: Calculate on `trailing_geometry_fee4_4d` with several hundred rows, memory watched.
