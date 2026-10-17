## Context

`MarketDataPort.get_bounds(ticker=, timeframe=)` (`ports/market_data.py:11`) returns
`StreamBounds` (`domain/contracts.py:296-308`): `ticker`, `timeframe`, `earliest_open_time_ms`,
`latest_open_time_ms`, `stream_state`. The HTTP client (`adapters/http/market_data_client.py:72-85`)
maps MDS `earliest_committed_open_time_ms` / `latest_committed_open_time_ms` / `state` onto it and
turns an unreachable MDS or a 5xx into `DependencyUnavailable` (HTTP 503) and any other non-200
into `UpstreamServiceError` with the upstream status. Sibling routes in `api/routers/market.py`
validate `symbol` (2-32 chars) and `timeframe` (2-8 chars), canonicalize the ticker with
`canonical_ticker` (`application/market/candles_window.py`) and delegate to a small use case.

## Decisions

1. **Route.** `GET /api/market/bounds`, query `symbol` and `timeframe`, same names, lengths and
   canonicalization as `candles-window` (`BTCUSDT` → `BTCUSDT.P`, `BTCUSDT.P` unchanged). Placed in
   the existing market router.
2. **Response.** A new frozen-style model with `extra="forbid"`, like the sibling DTOs:
   `{ "symbol": <canonical ticker>, "timeframe": <as requested, trimmed>,
   "earliest_open_time_ms": int, "latest_open_time_ms": int, "stream_state": str }`.
   The values are the `StreamBounds` fields unchanged. Times are open times in milliseconds,
   both bars exist (inclusive). `latest_open_time_ms` can be passed as `to_open_time_ms` to
   `candles-window` as is; the route does not compute an exclusive end.
3. **Use case.** `GetMarketBounds(market_data: MarketDataPort).execute(symbol, timeframe)`:
   canonicalize the symbol, validate the trimmed timeframe locally, call `get_bounds`, copy fields.
   `canonical_ticker()` validates only the symbol, so the use case SHALL check the timeframe itself
   through the existing domain `timeframe_ms()` (`domain/contracts.py`, the same mechanism the
   `MarketRange` validator uses for `candles-window`) BEFORE the port call. No second timeframe list
   is introduced. An unsupported timeframe raises `InvalidRequest` (HTTP 400) and the port is not
   called. No caching and no state: the answer must follow the
   committed stream, and MDS serves it cheaply.
4. **Errors.** Invalid `symbol` or unsupported `timeframe` (length violation or `timeframe_ms()` rejection) → 400 envelope (`InvalidRequest`, same as siblings);
   MDS unreachable or 5xx → 503; other MDS statuses pass through `UpstreamServiceError`
   (for example an unknown stream keeps MDS's own status). `stream_state` is reported, never
   interpreted: the route does not refuse a stream because of its state.
5. **Tests** use the fake `MarketDataPort` pattern of `tests/test_candles_window.py`.

## Risks

- `stream_state` values are owned by MDS; the route forwards them as free text.
- A stream with `earliest > latest` is not possible per the MDS contract; the route does not check.
