## 1. Cache

- [ ] 1.1 Authoritative entry per `(ticker, timeframe)`: `times` and per-period `values` arrays, `origin_ms`, `coverage_to_ms`; binary-search slicing; `truncated` outside the coverage.
- [ ] 1.2 Strategy Engine access for several EMA periods in one indicator plan (existing range API).
- [ ] 1.3 Build from Market Data Service stream bounds (inject the Market Data port into `GetEmaWindow`).

## 2. Preview and swap

- [ ] 2.1 Preview calculation `[from - 5 * period bars, to)` for the requested period; not stored.
- [ ] 2.2 One background build per `(ticker, timeframe)`, atomic publication, retry on the next request after a failure.

## 3. Verification

- [ ] 3.1 Tests: cold first request answered by a preview without waiting for the build; after the build every window is a cache hit and equals one continuous calculation; scrolling to earlier windows; request outside the coverage is `truncated`; failed build; one build only under concurrent requests.
- [ ] 3.2 Measure the cold preview time, the build time and the memory for the three periods; record here.
- [ ] 3.3 Browser check: scroll back through at least 100 trades; the overlay stays; no console errors.
- [ ] 3.4 `openspec validate research-ema-window-history-cache-v1 --strict`; update `research-market-ema-window-v1` on archive.
