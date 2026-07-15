# Recovery gap audit

Canonical recovery workspace created from the three user-provided archives on 2026-07-15.

## Baseline

- Research Service: 96 tests pass; persisted state is step 15 (`research-diagnostics-projection-v1`).
- Strategy Engine: baseline tests pass; its MDS client still computes `market_data_hash` locally.
- Market Data Service: source snapshot predates bounds/audit/hash/historical-read HTTP contracts.

## Missing work to restore

### Research Service

1. Step 16 `research-config-persistence-v1` production implementation and OpenSpec closure.
2. Step 17 `research-history-window-planning-v1` production implementation.
3. Strict legacy-to-wire typing helper and normative seam rules.
4. MDS-owned hash equality and historical-read orchestration.

### Strategy Engine

1. Accept and propagate MDS-owned `market_data_hash` instead of computing it.
2. Use the historical backtest candle endpoint with `expected_market_data_hash`.
3. Update the unified seam contract and consumer tests.

### Market Data Service

1. Read-only committed bounds endpoint.
2. Read-only explicit-range continuity audit endpoint.
3. MDS-owned canonical `market_data_hash`.
4. Separate historical backtest read endpoint that bypasses global readiness only after
   exact range/hash verification; runtime `/v1/candles` remains ready-only.
5. Deliver these changes as a patch relative to the supplied MDS snapshot.

## Recovery order

1. Restore Research step 16.
2. Restore Research step 17 contracts and orchestration.
3. Implement the MDS producer slice and generate a patch.
4. Update Strategy Engine and Research consumers.
5. Run a three-service synthetic SQLite E2E matrix.
6. Only then perform reference closure and remove the large legacy mirrors.


## Recovered historical read closure

The readiness gap is closed by a separate MDS historical endpoint bound to the continuity-audit hash. Research and Strategy use the same explicit range and MDS-owned provenance.
