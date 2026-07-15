# Single-instance backtest v1

## Purpose

`RunSingleInstanceBacktest` is the first complete authoritative Research Service path replacing the orchestration half of legacy `run_strategy_spec`.

```text
StrategyEvaluationRequest
→ Strategy Engine range evaluation
→ MDS MarketFrame
→ execution-contract acceptance
→ unified execution loop
→ realised trade accounting
→ SingleInstanceBacktestResult
```

No production code imports or executes `legacy_source`.

## Inputs

- explicit `run_id`;
- one canonical strategy instance and market range;
- Research-owned execution policy;
- Research-owned accounting policy;
- flag enabling managed-policy consumption.

## Service boundaries

Strategy Engine owns features, entries, standard exit policy and managed-policy decisions. MDS owns canonical OHLCV. Research Service owns fills, arbitration, position lifecycle and accounting.

The orchestrator rejects market-grid disagreement before simulation. Until MDS exposes canonical `market_data_hash`, alignment is enforced through market identity, bar count and every `open_time_ms`.

## Managed replay

For every opened position, the use case may request managed replay once. Under `bbb_v1`, `entry_price` sent to managed replay is the signal-bar close (`EntryFill.reference_price`), not the Research-owned slippage-adjusted fill.

## Output

`research_single_instance_backtest.v1` contains:

- full Strategy Engine evaluation and provenance;
- execution-contract acceptance evidence;
- ordered execution facts/events;
- realised accounting and immutable trade records.

Artifact persistence and HTTP activation are intentionally deferred to the next changes.
