# Proposal: Research History Window Planning v1

## Status

Deferred. This change is intentionally scheduled after the current Research Service BFF and backend cutover work. It is recorded now so that temporary first-request range behavior is not mistaken for the final architecture.

## Why

Legacy BBB often treated the entire local market database as one implicit input window. That behavior conflated three different concepts:

- the market history that actually exists;
- the period on which a research run should emit decisions and trades;
- the earlier history required to warm indicators, HTF contexts, lookbacks and stateful components.

The independent Market Data Service, Strategy Engine and Research Service require those responsibilities to be explicit. Without a shared window-planning contract:

- canonical EMA origin depends on the first requested chart window;
- full-history runs cannot be planned without probing failures;
- callers may duplicate or incorrectly estimate warmup;
- insufficient history may be silently accepted;
- Research Service and Strategy Engine may evaluate different effective windows.

## What changes

This cross-service change will define and implement:

- a Market Data Service stream-coverage API;
- explicit Research Service evaluation-range policies, including `full_available`;
- Strategy Engine calculation of required market-input history from the strategy spec and feature plan;
- strict separation of requested evaluation range and expanded market-input range;
- history policies for fully warmed versus partial-warmup evaluation;
- warmup and validity metadata in Strategy Engine responses;
- BFF use of coverage metadata for canonical indicator origins and chart planning;
- integration and performance acceptance across all three services.

## Out of scope

- changing indicator formulas or strategy semantics;
- moving research execution simulation into Strategy Engine;
- changing Workbench viewport behavior beyond consuming corrected metadata;
- implementing the future live bar-to-bar runtime wrapper.


## Historical read activation

After a successful audit, Research SHALL use `POST /v1/historical-candles` for its execution frame and SHALL pass the same `expected_market_data_hash` to Strategy Engine. Runtime `GET /v1/candles` is not used by backtest orchestration. No hidden warmup/pre-roll or repair is introduced.
