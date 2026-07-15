# Design

## Flow

`POST /api/research/backtests`

1. Parse `SingleInstanceBacktestRequest`.
2. Execute `RunSingleInstanceBacktest`.
3. Persist with `PersistSingleInstanceBacktest`.
4. Return `BacktestRunResponse` with HTTP 201.

The route is a transport adapter only. Strategy evaluation, market acquisition, execution, accounting and persistence remain application/domain responsibilities.

## Idempotency and conflicts

Run IDs are immutable. A second request using an already published `run_id` returns HTTP 409 with `run_already_exists`; it does not overwrite or mutate the existing artifact bundle.

## Response

The response is intentionally compact and includes run identity, completion status, trade/open-position counts, final equity, net PnL, artifact path, manifest contract version and Strategy Engine market-data hash. Detailed data remains in the immutable run bundle.

## Deferred job model

This v1 endpoint holds the request until completion. A later job/worker change may replace this with `202 Accepted` and run-status polling without changing execution semantics.
