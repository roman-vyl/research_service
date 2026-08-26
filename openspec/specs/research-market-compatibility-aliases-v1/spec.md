# Research Market Compatibility Aliases v1 Specification

## Purpose

Define the preserved legacy-parameter alias routes for candle and EMA
chart-overlay consumers.

## Requirements

### Requirement: Candle list alias

The service SHALL expose `GET /api/market/candles` with the legacy
parameters `symbol`, `timeframe`, `from`, and either `to` or
`to_open_time_ms`. A successful response SHALL be a list of `ChartBar`
objects produced through the canonical Market Data Service-backed
candle-window use case.

#### Scenario: Legacy candle request

- **WHEN** a client calls `GET /api/market/candles` with the legacy
  parameter names
- **THEN** the response is a `ChartBar` list produced by the same use case
  that backs `candles-window`.

### Requirement: EMA list alias

The service SHALL expose `GET /api/market/indicators/ema` with the legacy
parameters `symbol`, `timeframe`, `period`, `from`, and either `to` or
`to_open_time_ms`. A successful response SHALL be a list of
`IndicatorPoint` objects produced through the Strategy Engine-backed
EMA-window use case using canonical origin policy.

#### Scenario: Legacy EMA request

- **WHEN** a client calls `GET /api/market/indicators/ema` with the legacy
  parameter names
- **THEN** the response is an `IndicatorPoint` list produced by the same use
  case that backs `ema-window`.

### Requirement: No duplicate semantics

The compatibility routes SHALL NOT calculate indicators, access legacy
SQLite, or define independent caching rules.

#### Scenario: Layering check

- **WHEN** the compatibility route handlers are inspected
- **THEN** they delegate entirely to the candles-window/ema-window use
  cases and contain no independent calculation or caching logic.

### Requirement: Stable invalid range handling

Semantically invalid ranges SHALL return the Research Service
`invalid_request` error with HTTP 400.

#### Scenario: Invalid range on a legacy route

- **WHEN** a compatibility route receives a semantically invalid range
- **THEN** it returns HTTP 400 with `code=invalid_request`.
