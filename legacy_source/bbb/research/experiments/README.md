# Batch Experiment Management System

Capability: `research-experiments`  
Package: `research/experiments/`  
First execution module: **Experiment BatchRunner v1** (`batch_runner.py`)

Batch Experiment Management System v1 manages predefined **single-instance** candidate configs. It establishes reproducible batch execution, validation, failure isolation, summary extraction, and result persistence. It does **not** generate candidates, select winners, or optimize parameters.

Experiment BatchRunner v1 runs validated candidates sequentially and delegates every strategy run to the existing `ema_pullback` runner.

## What this is

- Batch orchestration above `research/strategies/ema_pullback`
- Input: batch spec JSON with a list of candidate strategy config paths
- Output: batch result JSON with per-candidate summaries and links to strategy reports

## What this is not (v1 non-goals)

- Not an optimizer, parameter sampler, or grid/random/Bayesian search
- Not entry-edge barrier diagnostics
- Not frontend, `research_api`, or Data Engine integration
- Not strategy semantics changes inside `ema_pullback`
- CLI is a **minimal local operator/debug entrypoint** — not the final UX
- No `--db-path` — the batch system does not own data source / DB selection

## Candidate config rule (v1)

Each candidate `strategy_config_path` must reference a config with **exactly one** `instances` item. Multi-instance configs are rejected at validation.

Batch-level `symbol` and `timeframe` must match each candidate config market.

## Example batch spec

See `research/experiments/specs/example_batch.json`.

## Commands

Validate only (no backtests):

```bash
python -m research.experiments.cli validate --spec research/experiments/specs/example_batch.json
```

Run batch:

```bash
python -m research.experiments.cli run-batch --spec research/experiments/specs/example_batch.json
```

## Batch result location

```text
research/experiments/results/batches/<experiment_id>.json
```

Batch results include reproducibility hashes (`batch_spec_hash`, `strategy_config_hash`), timing fields, and per-candidate `run_id` / `report_path` links to ordinary strategy reports under `research/results/runs/`.
