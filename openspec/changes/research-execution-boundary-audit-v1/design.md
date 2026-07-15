# Design: Research execution boundary audit v1

## Greenfield rule

`legacy_source/bbb/` is a disconnected reference mirror. Production code may inspect none of it at runtime and may not use it as a fallback. Legacy behavior is represented by audit notes and frozen expected fixtures only.

## Authoritative boundary

```text
StrategyEvaluationResult
+ MarketFrame
+ ExecutionPolicy
+ RunIdentity
-----------------------------
ResearchBacktestOrchestrator
  -> ExecutionSimulator
  -> AccountingEngine
  -> DiagnosticsProjector
  -> ArtifactStore
-----------------------------
BacktestResult
```

## Ownership

### Strategy Engine

Owns indicators, contexts, component states, entries, initial stop/take policy, standard signal exits, managed phase transitions, managed stop/take state and runtime-exit decisions.

### Research Service

Owns market-bar execution, entry/exit fills, gap handling, same-bar arbitration, position lifecycle, fees, slippage, realised PnL, equity, trade records, metrics, diagnostics projection and artifact persistence.

### Market Data Service

Owns canonical complete OHLCV ranges. Research Service reads the simulation MarketFrame independently and verifies it matches the strategy evaluation range and market identity.

## Porting rule

Legacy files are not copied as production modules. Each Research-owned behavior is rewritten behind typed contracts. Mixed files are split. Strategy-owned functions are not ported.

## First implementation scope

The first simulator supports one independent position per strategy instance, long/short entry, initial and managed stop/take candidates, signal/runtime exits, deterministic same-bar arbitration, fees and slippage. Partial exits and pyramiding remain out of scope.
