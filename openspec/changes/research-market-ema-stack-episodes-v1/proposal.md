## Why

Strategy Engine now serves the EMA stack episode history of a market without a strategy:
`POST /v1/ema-stack-episodes/history` (`ema-stack-episode-query-v1`, Strategy Engine 4f4f80c). It
returns whole finished episodes newest first in pages, the current (unbroken) episode, and pins every
page to one market data version (`expected_market_data_hash`, 409 `market_data_version_changed`).

The Research Workbench talks only to Research Service. To draw the episode layers agreed in the chart
mock-up (episode band, numbered touch zones, false breaks, waves S* to P, forming wave, episode lanes),
it needs that history through Research Service. Every object is computed by Engine; neither Research
Service nor the frontend computes or reshapes any of it.

## What Changes

- Add `POST /api/market/ema-stack-episodes/history`, a thin proxy to Strategy Engine
  `POST /v1/ema-stack-episodes/history`.
- The request body is forwarded unchanged; the Engine response body is returned unchanged (times in
  milliseconds as Engine sends them, no Decimal or timestamp conversion, no renamed fields).
- An Engine error response is returned with the same HTTP status and the same body (409
  `market_data_version_changed`, 422 invalid request, 503 market stream not ready, and any other).
  Strategy Engine unreachable is 503 `dependency_unavailable`.
- One Engine call per request. No server-side cache, no own validation of episode parameters, no own
  episode computation.

## Capabilities

### New Capabilities

- `research-market-ema-stack-episodes-v1`: the proxy route and its pass-through rules.

## Non-Goals

- A second server cache: Engine has its LRU per market data version, the frontend keeps the
  episodes it received.
- Any episode computation, defaulting or validation in Research Service.
- Conversion of times to Unix seconds or of any value.
- Reading the episode from run diagnostics (`/range/diagnostics`).
- Frontend changes (separate change in `research_frontend`).

## Impact

- Research Service: Strategy Engine port and HTTP client (one method), one market use case, one route,
  one error type passed through verbatim, tests.
- Strategy Engine, Market Data Service: none.
