# Trade Accounting v1

The new accounting boundary consumes only new Research Service contracts:

```text
ExecutionLoopResult
+ MarketFrame
+ AccountingPolicy
→ TradeAccountingResult
```

It calculates actual-fill notionals, entry/exit fees, side-aware gross and net PnL, additive realised equity, and path diagnostics (MFE, MAE, capture and giveback). A position left open at the end of the requested range remains unrealised and does not change equity.

This is a clean reimplementation of Research-owned semantics. `legacy_source` is used only to verify historical invariants.
