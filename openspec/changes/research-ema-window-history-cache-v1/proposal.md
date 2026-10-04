## Why

Scrolling the Workbench chart backwards through trades loses the EMA overlay. Reproduced in the browser
(no console errors, every request 200): `GET /api/market/ema-window` returns `points: []`,
`truncated: true`, `calculation_origin_ms` later than the requested window.

Root cause (`GetEmaWindow`): the process-local cache starts the EMA series at the first request after the
process started and only grows to the right; a later request that starts before that origin is sliced
from a series that does not reach back and answers empty.

Measured on the development MacBook (Strategy Engine, BTCUSDT.P 5m, 686 565 bars):

- time is linear in bars and dominated by candle read and serialisation: 25 000 bars 0.5 s, full history
  12.8 s for **three periods in one request** (one period costs the same; three separate full-history
  requests about 50 s);
- an EMA calculated from a range start is seeded by the first close: against a series started 5 000 bars
  earlier it differs by 50 USDT on the first bar, 7 after 1 000 bars, 1 after 2 000, 0.13 after 3 000,
  0.002 after 5 000 (EMA 1000);
- one full-history period held as Python objects costs about 0.33 GB, as two numeric arrays about 11 MB.

## What Changes

- Strategy Engine calculates the **full history once** for EMA 200/500/1000 in one call; the result is
  kept as compact arrays and is the authoritative cache. After it exists, every window is a slice.
- While that build runs (about 13 s), requests are answered from a **preview window** with warm-up, so
  EMAs appear within about a second.
- The preview is replaced by the authoritative cache in one atomic swap.
- History bounds come from the existing Market Data Service bounds (`get_bounds`), no new setting.

Public routes, query parameters and response field names do not change; the frontend does not change.

## Capabilities

### Modified Capabilities

- `research-market-ema-window-v1`: cache behaviour and origin metadata.

## Non-Goals

- Lazy expansion, chunking, recalculation when the user scrolls left or right, joining of independently
  calculated pieces.
- Handling of bars that arrive after the history was built (live bars): a process restart rebuilds.
- The three-service canonical-origin rollout of `research-history-window-planning-v1` (this change reads
  the bounds that Market Data Service already serves).
- Any frontend change.

## Impact

- Research Service: `application/market/ema_window.py` (needs the Market Data port for bounds),
  tests.
- Strategy Engine, Market Data Service: none (existing indicator range API with several features in
  one plan; existing stream bounds route).
