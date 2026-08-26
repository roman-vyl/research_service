# Strategy Engine / Research Service ownership

Normative for both `strategy_engine` and `research_service`. Salvaged from the
retired `19_unified_strategy_research_seam_contract.md` (extraction-era doc,
deleted 2026-08-26); this is the part of it that is still live architecture,
not extraction history.

## Strategy Engine owns

- strategy-spec normalization and semantic validation;
- feature-plan construction;
- indicator, context and component evaluation;
- entry decisions;
- initial stop/take policy;
- standard signal exits;
- managed phase, stop, take-profile and runtime-exit policy decisions;
- strategy evidence and semantic event identity.

## Research Service owns

- research-run orchestration;
- canonical OHLCV acquisition for simulation;
- entry and exit fill execution;
- gap/open handling and same-bar arbitration;
- position lifecycle;
- fees, slippage, PnL, equity and metrics;
- trade records, artifacts, diagnostics projection and Workbench DTOs.

## Alignment invariant

Before simulation, Research Service must reject any mismatch between the
Strategy Engine decision frame and the MDS execution frame:

- ticker;
- timeframe;
- requested evaluation range;
- ordered timestamps and bar count;
- market-data identity/hash when available.

No local indicator recalculation, interpolation, silent truncation or legacy
fallback is permitted.
