## 1. Proxy

- [x] 1.1 Strategy Engine port and HTTP client: `query_ema_stack_episode_history(body)` posts to `/v1/ema-stack-episodes/history`, returns the JSON object on 200, raises `UpstreamResponse` with the status and body otherwise, `DependencyUnavailable` on transport failure.
- [x] 1.2 `UpstreamResponse` error and its handler: same status, same body; non-object body wrapped in the standard envelope.
- [x] 1.3 Use case `GetEmaStackEpisodeHistory` and route `POST /api/market/ema-stack-episodes/history`, body forwarded unchanged, response returned unchanged.

## 2. Verification

- [x] 2.1 Tests through the app with the real HTTP client on a mocked Engine transport: body forwarded unchanged; 200 body returned unchanged (times in ms, `current`, `next_before_start_ms`, hashes); 409 `market_data_version_changed`, 422 and 503 passed through with status and body; Engine unreachable is 503 `dependency_unavailable`; one Engine call per request, a repeated request calls Engine again.
- [ ] 2.2 Check on the development MacBook against Strategy Engine 4f4f80c: first page, second page with `expected_market_data_hash`, wrong pin gives 409.
- [ ] 2.3 `openspec validate research-market-ema-stack-episodes-v1 --strict`; sync the spec on archive.
