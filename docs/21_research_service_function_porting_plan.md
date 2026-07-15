# Research Service function-by-function porting plan

## Status

This is the authoritative staged plan for rebuilding the Research-owned half of the legacy BBB call graph. It complements `docs/19_unified_strategy_research_seam_contract.md` and supersedes file-level copy plans for production implementation.

`legacy_source/bbb/` is a disconnected mirror used only for reading, audit, provenance and frozen parity fixtures. Production code must not import or execute it.

## Porting rule

For every legacy caller/callee identified by the seam audit:

1. locate all callers and side effects;
2. map Strategy-owned work to a concrete Strategy Engine endpoint and response field;
3. isolate the remaining Research-owned behavior;
4. define transport-neutral Research domain contracts;
5. implement the behavior from scratch under `src/research_service`;
6. add frozen reviewed acceptance fixtures;
7. wire the new use case into the new orchestration path;
8. never add a legacy runtime fallback.

## Staged changes

1. `research-strategy-evaluation-contract-v1` — implemented
   - consume and validate the Strategy Engine range contract.
2. `research-market-frame-acquisition-v1` — implemented
   - acquire the matching MDS frame and prove bar-grid identity.
3. `research-entry-execution-v1` — implemented
   - create deterministic entry fills and one open position per instance.
4. `research-initial-protection-v1` — implemented
   - resolve Strategy-owned stop/take ratios into absolute Research execution levels.
5. `research-static-exit-arbitration-v1` — implemented
   - stop, take and signal candidates; gap and same-bar priority.
6. `research-managed-policy-consumption-v1` — implemented
   - consume managed replay states/events with N+1 timing.
7. `research-unified-exit-arbitration-v1` — implemented
   - combine static and managed candidates under BBB v1 priority.
8. `research-unified-execution-loop-v1` — implemented
   - run one position state machine across the market range.
9. `research-trade-accounting-v1` — implemented
   - fees, PnL, equity and trade-path diagnostics.
10. `research-single-instance-backtest-v1` — implemented
    - compose Strategy Engine, MDS, execution and accounting.
11. `research-run-artifacts-v1` — implemented
    - atomically publish immutable, versioned run bundles.
12. `research-backtest-api-v1` — implemented
    - activate `POST /api/research/backtests`.
13. `research-batch-experiments-v1` — implemented
    - sequential variants first; bounded concurrency later.
14. `research-results-bff-v1` — implemented
    - runs, trades and metrics endpoints from the new artifact store.
15. `research-diagnostics-projection-v1` — implemented
    - Strategy evidence plus Research execution events into Workbench DTOs.
16. `research-config-persistence-v1`
    - serialize/save/select config state.
17. deferred `research-history-window-planning-v1`
    - coverage, warmup, canonical origin and mandatory MDS-owned `market_data_hash` comparison.
18. reference closure
    - replace executable legacy parity with frozen fixtures and remove the mirror from final distribution when no longer needed.

## Current implementation

`research-entry-execution-v1`, `research-initial-protection-v1`, `research-static-exit-arbitration-v1`, `research-managed-policy-consumption-v1`, `research-unified-exit-arbitration-v1` and `research-unified-execution-loop-v1` are implemented. Single-instance orchestration, atomic run artifacts, the synchronous backtest HTTP API and sequential batch experiments are implemented. The next production change is `research-config-persistence-v1`.


## Stage status

- Entry execution: implemented.
- Initial protection: implemented.
- Static exit arbitration: implemented.
- Managed policy consumption: implemented.
- Unified exit arbitration: implemented.
- Unified execution loop/state machine: implemented.
- Trade accounting: implemented.
- Single-instance backtest orchestration: implemented.
- Atomic run artifacts: implemented.
- Backtest HTTP API: implemented.
- Results/runs BFF read layer: implemented.
- Diagnostics projection: implemented.
- Config persistence: next.
