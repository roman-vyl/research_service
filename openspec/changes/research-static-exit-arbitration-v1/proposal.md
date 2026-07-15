# Proposal: Research static exit arbitration v1

Rebuild the Research-owned static exit half of the legacy BBB execution seam. Consume Strategy Engine signal-exit policy plus `PositionState.initial_protection`, inspect MDS OHLC, collect stop/take/signal candidates, apply reviewed same-bar priority, and produce a deterministic `ExitFill` without importing legacy runtime code.
