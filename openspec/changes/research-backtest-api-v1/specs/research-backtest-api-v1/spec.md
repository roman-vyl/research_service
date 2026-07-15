# Research Backtest API v1 Specification

## Requirements

1. `POST /api/research/backtests` SHALL accept `SingleInstanceBacktestRequest`.
2. The endpoint SHALL use the authoritative Strategy Engine and Market Data Service ports through the existing single-instance orchestration use case.
3. A successful run SHALL be atomically persisted before the endpoint returns success.
4. Success SHALL return HTTP 201 and `research_backtest_api.v1`.
5. The response SHALL identify the run, instance, realised trade count, open-position count, final equity, net PnL and artifact bundle.
6. An existing immutable `run_id` SHALL return HTTP 409 `run_already_exists`.
7. The route SHALL NOT import or execute `legacy_source`.
8. The route SHALL NOT implement strategy, execution or accounting semantics.
