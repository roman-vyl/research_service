## Why

A backtest chart whose window starts in the first ~500 bars of the stored history fails with
"Strategy Engine indicator request failed". For an EMA outside the cached stack (for example
period 100) the EMA-window route asks Strategy Engine for `5 * period` bars of warmup before the
requested start, which reaches before the first stored bar; Market Data answers 422
`range_out_of_bounds` and Strategy Engine answers 502. Reproduced on run
`run_d4c5b23fd8944523b64bbd06bd31f2e9` (BTCUSDT.P 5m, trade #1 of 2020-03-29, history starts
2020-03-25): `period=100` returns 502, `period=200` returns 200. The route code has not changed
since 2026-10-04, so this is an old defect that only shows near the start of history.

The cold stack preview (periods 200/500/1000, 5000 bars of warmup) has the same defect; it is
hidden only while the authoritative cache already exists.

## What Changes

- One rule for both previews: the warmup of a preview calculation never starts before the
  market's first stored bar (`earliest_open_time_ms` from Market Data bounds). It applies to the
  one-off EMA preview and to the 200/500/1000 preview. The authoritative build already starts at
  that bound.
- Bounds that cannot be read are not guessed: the existing upstream error propagates and no
  Strategy Engine call is made (the stack preview slot is released).
- A requested range that ends at or before the first stored bar is rejected as an invalid
  request instead of failing inside the range model.

## Out of Scope

Strategy Engine and Market Data, the frontend, cache semantics, the periods of the stack, and the
number of warmup bars.

## Capabilities

### Modified Capabilities

- `research-market-ema-window-v1`: Preview warmup lower bound.
