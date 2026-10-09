## 1. Proxy

- [x] 1.1 Strategy Engine port and HTTP client: `query_ema_stack_episode_history(body)` posts to `/v1/ema-stack-episodes/history`, returns the JSON object on 200, raises `UpstreamResponse` with the status and body otherwise, `DependencyUnavailable` on transport failure.
- [x] 1.2 `UpstreamResponse` error and its handler: same status, same body; non-object body wrapped in the standard envelope.
- [x] 1.3 Use case `GetEmaStackEpisodeHistory` and route `POST /api/market/ema-stack-episodes/history`, body forwarded unchanged, response returned unchanged.

- [x] 1.4 `POST /api/research/strategies/{strategy_id}/feature-plan` passed through to Engine with the same rules; `strategy_id` limited to `[A-Za-z0-9_-]{1,64}`.

## 2. Verification

- [x] 2.1 Tests through the app with the real HTTP client on a mocked Engine transport: body forwarded unchanged; 200 body returned unchanged (times in ms, `current`, `next_before_start_ms`, hashes); 409 `market_data_version_changed`, 422 and 503 passed through with status and body; Engine unreachable is 503 `dependency_unavailable`; one Engine call per request, a repeated request calls Engine again; feature plan forwarded and returned unchanged, its Engine error passed through, an odd `strategy_id` rejected without an Engine call.
- [x] 2.2 Check on the development MacBook against Strategy Engine 4f4f80c: first page, second page with `expected_market_data_hash`, wrong pin gives 409.
  - 2026-10-09 (owner-approved smoke, branch 61c3c23 from source on 8096, Engine 4f4f80c on 8090): BTCUSDT.P 5m 200/500/1000 long limit 500 → 200, 430 episodes, `next_before_start_ms` null, byte-identical to Engine; limit 100 → page 1 100 episodes, page 2 with page 1's pin 100 older episodes; wrong pin → 409 `market_data_version_changed` with both hashes, body equal to Engine's except `request_id`; bad parameters → 422; feature plan equal to Engine for no section (`episode_params_by_ref` null), one ref (500/1000/2000/24/24) and two refs; unknown strategy 404. Cold 12.3–13.6 s, repeat 0.07–0.11 s.
- [x] 2.3 `openspec validate research-market-ema-stack-episodes-v1 --strict`; sync the spec on archive.
