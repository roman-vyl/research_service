## Why

The Runtime Dashboard needs to draw the latest candles of a market. The Workbench frontend can ask
`GET /api/market/candles-window` for a range, but it cannot learn which range exists: the
Research Chart takes its history limits from a run's report, and `candles-window` answers
exactly the requested range or fails (`research-market-candles-window-v1`, "Complete success
only"). The browser clock does not say which bars Market Data Service (MDS) has committed.

Research Service already knows the answer. `MarketDataPort.get_bounds` returns the committed
stream bounds of a ticker/timeframe (`StreamBounds`, MDS `GET /v1/streams/{ticker}/{timeframe}/bounds`)
and is used internally by the EMA window builder. It is not exposed to the frontend.

## What Changes

- New read-only route `GET /api/market/bounds?symbol=&timeframe=` that returns the committed
  bounds of one market, taken from `MarketDataPort.get_bounds` without any calculation.
- Query names, ticker canonicalization and error envelope follow the sibling `/api/market/*`
  routes.

## Out of Scope

Any calculation or adjustment of bounds, caching, continuity or gap checks, listing of
available markets, changes to Market Data Service, to `candles-window` or any other route,
frontend changes (separate change in `research_frontend`).

## Capabilities

### New Capabilities

- `research-market-bounds-v1`: the read-only market bounds route.

## Impact

- `src/research_service/api/routers/market.py` (new route), `src/research_service/api/contracts/chart.py`
  or a neighbouring contracts module (response model), new `src/research_service/application/market/bounds.py`
  (thin use case, same shape as `GetCandlesWindow`), wiring in `runtime/wiring.py`/`runtime/services.py`,
  `tests/test_market_bounds.py`. No dependency, port or MDS change.
