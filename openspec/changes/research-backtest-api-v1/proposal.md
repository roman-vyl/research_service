# Proposal: Research Backtest API v1

Expose the completed single-instance backtest orchestration and atomic run persistence through the preserved Research BFF route `POST /api/research/backtests`.

The endpoint is synchronous in v1, returns a compact completion summary, and adds no new strategy, execution or accounting semantics.
