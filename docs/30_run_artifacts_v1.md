# Run Artifacts v1

`PersistSingleInstanceBacktest` persists the output of the single-instance backtest use case without changing execution semantics.

## Directory

```text
var/runs/<run_id>/
├── manifest.json
├── request.json
├── strategy_evaluation.json
├── execution_events.json
├── trades.json
├── metrics.json
└── result.json
```

## Publication guarantee

The directory is prepared under a hidden temporary sibling and becomes visible only through one atomic rename. A failed write leaves no published run. Existing run IDs cannot be replaced.

## Provenance

`manifest.json` records the contract versions and the Strategy Engine `market_data_hash`. Until MDS exposes its own canonical hash, this value is provenance rather than a cross-service equality proof.

Every non-manifest file is recorded with SHA-256 and byte size.
