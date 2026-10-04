## 1. Cache

- [x] 1.1 Authoritative entry per `(ticker, timeframe)`: `times` and per-period `values` arrays, `origin_ms`, `coverage_to_ms`; binary-search slicing; `truncated` outside the coverage.
- [x] 1.2 Strategy Engine access for several EMA periods in one indicator plan (existing range API).
- [x] 1.3 Build from Market Data Service stream bounds (inject the Market Data port into `GetEmaWindow`).

## 2. Preview and swap

- [x] 2.1 Implement one temporary preview entry per `(ticker, timeframe)` containing EMA 200/500/1000 from one Engine call over `[from - 5 * max(periods) bars, to)`; slice it for all three requests and never expand it.
- [x] 2.2 Implement the `EMPTY -> PREVIEW -> FULL` state machine: one background full build, atomic replacement of preview by full, and retry on the next request after a failure.

## 3. Verification

- [x] 3.1 Tests: cold first request makes one three-EMA preview call with a 5 000-bar warm-up without waiting for the build; EMA 500/1000 requests reuse that preview; preview never expands and truncates outside its coverage; after the build every window is a full-entry cache hit and equals one continuous calculation; scrolling to earlier windows; failed build; one build only under concurrent requests; atomic `PREVIEW -> FULL` promotion.
- [x] 3.2 Measured on the development MacBook against BTCUSDT.P 5m: 25 000-bar cold preview 0.535 s; preview slices for EMA 500/1000 0.021/0.028 s; full promotion 11.507 s for 686 602 bars; compact arrays 20.95 MiB payload, process RSS delta about 126 MiB including HTTP/JSON parsing and allocator high-water.
- [x] 3.3 Browser check: moved from trade 260 to trade 159 (101 trades back); the 25 000-bar chart retained visible EMA 200/500/1000 overlays; browser console warnings/errors were empty.
- [x] 3.4 `openspec validate research-ema-window-history-cache-v1 --strict`; update `research-market-ema-window-v1` on archive.
