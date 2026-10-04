## Context

`GetEmaWindow` keeps `(ticker, timeframe, period) -> entry(origin_ms, coverage_to_ms, points)`; the entry
starts at the first request and is extended only to the right by a separately calculated suffix. Strategy
Engine seeds every calculation with the first close of its range and has no warm-up.

## Source of the history bounds

Two sources already exist; neither needs a new setting.

1. **Market Data Service stream bounds.** `HttpMarketDataClient.get_bounds(ticker, timeframe)`
   (`adapters/http/market_data_client.py`) calls `GET /v1/streams/{ticker}/{timeframe}/bounds` and returns
   `earliest_open_time_ms` / `latest_open_time_ms` (`earliest_committed_open_time_ms`,
   `latest_committed_open_time_ms` in the payload). `ResolveBacktestWindow`
   (`application/backtests/history_window.py`, `range_policy=full_available`) already uses it as the
   history of a ticker. This is the EMA cache bound: the series is calculated from the earliest committed
   bar to the latest one at build time.
2. **The run's own window.** Every run records the market range it was calculated on:
   `request.json` `range {from_ms, to_ms}` with `range_policy`, and `strategy_evaluation.json`
   `market {ticker, timeframe, from_ms, to_ms}`, `bar_count`, `market_data_hash` (for example
   `run_25aa140e…`: 1585132500000 .. 1790543700000, 684 704 bars). The frontend already holds it
   (`runDetail.result.strategy_evaluation.market`). It describes which bars the run traded; it is not an
   input of the EMA cache, because the route has no run parameter and one series serves all runs of a
   ticker. A run window that starts after the earliest committed bar sees the same values from the
   second thousand bars on (warm-up residual below 0.005 USDT after 5 000 bars).

## Decisions

### Authoritative cache

One entry per `(ticker, timeframe)` holding `times` (int64 seconds) and one float64 `values` array per
period for the periods 200, 500, 1000 (the EMA stack of the strategies the Workbench shows; named
constant), plus `origin_ms` (earliest committed bar) and `coverage_to_ms` (latest committed bar + step at
build time). Built by **one** Strategy Engine indicator call with three EMA features over
`[earliest, latest + step)`. About 11 MB per period.

After the swap a request is a binary-search slice of the arrays: no Engine call, `cache_hit=true`,
`calculation_origin_ms = origin_ms`. A request outside `[origin, coverage_to)` is answered with the part
inside it and `truncated=true`; it never triggers a calculation.

### Preview while the cache is being built

The first request for `(ticker, timeframe)` for a period in the set starts the full build in a background
thread and, in parallel, creates one temporary preview entry for all three periods with one Engine call.
The call covers `[from - 5 * max(periods) bars, to)`, i.e. a 5 000-bar warm-up for the fixed
`(200, 500, 1000)` stack. The entry has the same compact `times` plus per-period `values` shape as the
full entry, but is marked as preview and has only that fixed coverage.

The triggering request is served from the new entry with `cache_hit=false`. Further requests for 200,
500 or 1000 during the full build are binary-search slices of the same preview entry and report
`cache_hit=true` when fully covered. A request outside the preview coverage receives the available slice
with `truncated=true`; it does not expand or replace the preview and does not make another Engine call.
`calculation_origin_ms` is the start of the preview call, including warm-up. A period outside the fixed
stack is answered by an uncached one-period preview and does not participate in this state machine.

Thus a supported stack has exactly three states: `EMPTY -> PREVIEW[200,500,1000] ->
FULL[200,500,1000]`. There are no per-period preview entries and no long-lived preview cache.

### Atomic swap

The build assembles an immutable full entry and publishes it by atomically replacing the preview entry
under a lock; requests read the reference once. There is at most one build per `(ticker, timeframe)`; a
failed build is logged, leaves the preview entry in place, and the next request starts a new attempt.

### Why the preview is stored temporarily

The preview exists only for the roughly 13 seconds of the full build, but retaining it avoids two repeated
candle reads when the frontend requests EMA 500 and 1000 after EMA 200. It is not a navigation cache:
it has fixed coverage, never expands, and disappears in the same atomic publication that installs the
authoritative full entry.

## Risks

- A cold process spends about 13 s of Engine and Market Data time on the full build while one multi-EMA
  preview call also reads candles. Acceptable for a single-user research tool; measured separately in
  the tasks.
- Bars committed after the build are not in the series until the process restarts. Out of scope by
  decision.
