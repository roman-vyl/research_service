# Design

## Boundary

Input:

- `SingleInstanceBacktestRequest`
- matching `SingleInstanceBacktestResult`

Output:

- immutable run directory;
- versioned manifest with SHA-256 and byte size for every content artifact.

## Atomicity

All files are written to a temporary sibling directory. The directory is published with one same-filesystem atomic rename only after all files are written. Existing run IDs are immutable and cannot be overwritten.

## Files

- `manifest.json`
- `request.json`
- `strategy_evaluation.json`
- `execution_events.json`
- `trades.json`
- `metrics.json`
- `result.json`

JSON uses Pydantic JSON-mode serialization, stable key ordering, UTF-8 and a trailing newline. Decimal values remain exact JSON strings.
