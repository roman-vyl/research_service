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
thread and, in parallel, is answered by a preview: one Engine call for
`[from - 5 * period bars, to)`, served from `from` on, `cache_hit=false`,
`calculation_origin_ms` = start of that call (earlier than the requested start). Requests that arrive
during the build are answered the same way. A period outside the set is answered by previews only.
Previews are not stored.

### Atomic swap

The build assembles an immutable entry and publishes it with one assignment under a lock; requests read
the reference once. There is at most one build per `(ticker, timeframe)`; a failed build is logged, leaves
the previews in place, and the next request starts a new attempt.

### Why the preview does not need a cache

It is used only for the first seconds of a process; a window of 25 000 bars costs 0.5 s. The simplicity
of "preview or slice" is worth more than reusing it.

## Risks

- A cold process spends about 13 s of Engine and Market Data time on the build while previews also call
  Engine. Acceptable for a single-user research tool; measured separately in the tasks.
- Bars committed after the build are not in the series until the process restarts. Out of scope by
  decision.
