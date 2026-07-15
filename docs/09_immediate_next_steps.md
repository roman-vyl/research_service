# Immediate next steps

Completed through step 15 of the function-by-function porting plan.

1. Implement `research-config-persistence-v1`: serialize, save and select Research-owned config state while Strategy Engine remains the semantic validator.
2. Complete deferred `research-history-window-planning-v1`: MDS coverage, warmup planning, canonical EMA origin and mandatory MDS-owned `market_data_hash` comparison.
3. Replace remaining executable mirror-based parity with frozen fixtures, then remove `legacy_source` from final distribution when no longer needed.
