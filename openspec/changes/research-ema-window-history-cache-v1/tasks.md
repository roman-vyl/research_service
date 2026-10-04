## 1. Cache

- [ ] 1.1 Authoritative entry per `(ticker, timeframe)`: `times` and per-period `values` arrays, `origin_ms`, `coverage_to_ms`; binary-search slicing; `truncated` outside the coverage.
- [ ] 1.2 Strategy Engine access for several EMA periods in one indicator plan (existing range API).
- [ ] 1.3 Build from Market Data Service stream bounds (inject the Market Data port into `GetEmaWindow`).

## 2. Preview and swap

- [ ] 2.1 Implement one temporary preview entry per `(ticker, timeframe)` containing EMA 200/500/1000 from one Engine call over `[from - 5 * max(periods) bars, to)`; slice it for all three requests and never expand it.
- [ ] 2.2 Implement the `EMPTY -> PREVIEW -> FULL` state machine: one background full build, atomic replacement of preview by full, and retry on the next request after a failure.

## 3. Verification

- [ ] 3.1 Tests: cold first request makes one three-EMA preview call with a 5 000-bar warm-up without waiting for the build; EMA 500/1000 requests reuse that preview; preview never expands and truncates outside its coverage; after the build every window is a full-entry cache hit and equals one continuous calculation; scrolling to earlier windows; failed build; one build only under concurrent requests; atomic `PREVIEW -> FULL` promotion.
- [ ] 3.2 Measure the cold preview time, the build time and the memory for the three periods; record here.
- [ ] 3.3 Browser check: scroll back through at least 100 trades; the overlay stays; no console errors.
- [ ] 3.4 `openspec validate research-ema-window-history-cache-v1 --strict`; update `research-market-ema-window-v1` on archive.
