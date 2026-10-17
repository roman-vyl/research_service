## 1. Route

- [ ] 1.1 Response model `MarketBoundsBundle` (name open) with `extra="forbid"` next to the other chart/market contracts.
- [ ] 1.2 `application/market/bounds.py`: `GetMarketBounds` use case (canonicalize symbol, validate trimmed timeframe via existing domain `timeframe_ms()` before the port call → `InvalidRequest`, call `get_bounds`, copy fields), exported like `GetCandlesWindow`.
- [ ] 1.3 Wire the use case in `runtime/wiring.py` and `runtime/services.py`.
- [ ] 1.4 `GET /api/market/bounds` in `api/routers/market.py` with `symbol`/`timeframe` validation identical to siblings.

## 2. Tests

- [ ] 2.1 `tests/test_market_bounds.py` with a fake `MarketDataPort`: forwarded values, canonical ticker, exact five-field shape, port called on every request.
- [ ] 2.2 Errors: invalid symbol → 400 and no port call; unsupported textual timeframe with valid query length (e.g. `7x`) → 400 and `get_bounds` call count = 0; port raising `DependencyUnavailable` → 503; port raising `UpstreamServiceError(404)` → 404.
- [ ] 2.3 Existing market tests unchanged and green; `make`/pytest and strict OpenSpec validation green.

## 3. Acceptance

- [ ] 3.1 On the Mac stack (on the owner's word): `curl 'http://127.0.0.1:8095/api/market/bounds?symbol=ETHUSDT.P&timeframe=5m'` returns the MDS bounds and `latest_open_time_ms` works as `to_open_time_ms` of `candles-window`.
