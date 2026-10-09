## Context

Engine owns the episode semantics and the history route (`ema-stack-episode-query-v1`):

- request `{market: {ticker, base_timeframe}, episode: {fast_period, anchor_period, slow_period,
  window_bars?, break_bars?}, side: long|short, page?: {before_start_ms, limit}, expected_market_data_hash?}`;
- response: `history_id`, effective `params`, `params_hash`, `market_data_hash`, `earliest_ms`, `as_of_ms`,
  `episodes` (whole finished episodes, newest first), `next_before_start_ms`, `current`;
- errors in the envelope `{error, message, details, request_id}`: 409 `market_data_version_changed`
  (both hashes in `details`), 422 `invalid_request`, 503 when the market stream is not ready.

Research Service already uses the same error envelope, so an Engine error body is a valid Research
Service error body as it is.

## Decisions

### Route mirrors Engine

`POST /api/market/ema-stack-episodes/history` under the existing market BFF prefix, with the Engine
request body. A POST body is forwarded byte-for-byte as JSON, so the proxy needs no parameter
mapping and no knowledge of episode keys; new optional Engine keys reach Engine without a Research
Service change.

### No validation, no defaults

The body is accepted as any JSON object and forwarded. Engine's canonical parser decides (missing
period, ordering, unknown keys, `limit` bounds) and its 422 is returned. Research Service does not
canonicalise the ticker either: the frontend sends what Engine expects (`BTCUSDT.P`).

### Response unchanged

The route returns Engine's JSON object as it is, without a response model, so no field is dropped,
renamed or converted. Times stay in milliseconds. This differs on purpose from the chart DTO routes
(`ema-window`, `candles-window`), which convert to Unix seconds: here the frontend receives Engine's
contract.

### Errors passed through

A non-200 Engine response raises `UpstreamResponse(status_code, body)`; its handler returns the same
status and the same JSON body. A body that is not a JSON object is wrapped in the standard envelope
(`upstream_service_error`) with the same status. A transport failure or timeout is 503
`dependency_unavailable` with `service: strategy_engine`. A 200 whose body is not a JSON object is 502
`upstream_service_error`.

The existing `UpstreamServiceError` is not used for Engine responses, because it rewrites 5xx to 502
and replaces the error code, which would hide 503 and 409 from the frontend.

### No cache

One Engine call per request. A repeated page is cheap in Engine (LRU per market and parameters, served
without recomputing while the data version is unchanged). The frontend keeps finished episodes by
start and refreshes `current`.

### Timeout

The existing Strategy Engine client timeout (60 s) covers a cold history request (about 10 to 15 s for
BTCUSDT.P 5m full history measured on the development MacBook).

## Risks

- The route exposes Engine's contract directly: an incompatible Engine change reaches the frontend
  without a Research Service guard. Accepted: Engine versions its contract, and a proxy that
  re-validated it would duplicate Engine semantics.
