# Backtest API v1

`research-backtest-api-v1` activates the first complete Research Service backtest through HTTP:

```text
POST /api/research/backtests
→ RunSingleInstanceBacktest
→ PersistSingleInstanceBacktest
→ 201 BacktestRunResponse
```

The endpoint accepts the same immutable application request used by the internal orchestrator. It synchronously evaluates the strategy through Strategy Engine, obtains the matching market frame from MDS, runs execution and accounting, and atomically publishes `var/runs/<run_id>/` before returning.

The response contract is `research_backtest_api.v1`. It is deliberately a compact completion summary; complete evaluation, execution events, trades, metrics and result data are stored in the run artifact bundle.

Run IDs are immutable. Reusing a published ID returns `409 run_already_exists` and leaves the existing bundle unchanged.

The synchronous request model is an initial transport choice. A later worker/job stage may introduce `202 Accepted` and status polling without changing the backtest domain contract.
