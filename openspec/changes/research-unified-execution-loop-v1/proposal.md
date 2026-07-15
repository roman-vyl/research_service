# Proposal: Research Unified Execution Loop v1

Build the first complete Research-owned bar-by-bar position state machine over the already ported entry, initial-protection, static-exit, managed-policy and unified-arbitration slices. The loop consumes Strategy Engine decisions and MDS candles, opens at most one position per instance, applies exits only to positions present at bar open, preserves no-same-bar-reentry behavior and emits deterministic execution facts without calculating fees or PnL.
