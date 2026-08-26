# Research Market Candles Window v1 Specification

## Purpose

Define the preserved Workbench candles-window BFF route backed by Market
Data Service.

## Requirements

### Requirement: Preserved Workbench route

Research Service SHALL expose `GET /api/market/candles-window` with
BBB-compatible query names and response fields.

#### Scenario: Workbench requests a candle window

- **WHEN** the Workbench frontend calls `GET /api/market/candles-window`
  with its existing query parameters
- **THEN** the response uses the same field names it always has.

### Requirement: Canonical MDS request

The route SHALL call Market Data Service through `MarketDataPort` using
canonical `.P` ticker identity, textual timeframe, and an aligned half-open
millisecond range. Legacy `BTCUSDT` SHALL map to `BTCUSDT.P`; canonical
`BTCUSDT.P` SHALL remain unchanged.

#### Scenario: Legacy ticker is supplied

- **WHEN** a request supplies the legacy symbol `BTCUSDT`
- **THEN** the Market Data Service request uses canonical `BTCUSDT.P`.

### Requirement: Workbench chart DTO

Every returned candle SHALL contain `time` in Unix seconds and numeric
`open`, `high`, `low`, `close`, and optional `volume` fields. The response
SHALL contain coverage fields `requested_from_ms`, `requested_to_ms`,
`actual_from_ms`, `actual_to_ms`, and `truncated`.

#### Scenario: Successful response shape

- **WHEN** the route returns candles
- **THEN** each candle carries Unix-second `time` and the coverage fields
  are present alongside the candle list.

### Requirement: Complete success only

A successful response SHALL represent the complete requested grid and SHALL
report exact coverage with `truncated=false`. The route SHALL NOT synthesize
partial success when Market Data Service refuses an unavailable or
out-of-bounds range.

#### Scenario: Requested range exceeds available data

- **WHEN** Market Data Service cannot serve the complete requested range
- **THEN** the route SHALL NOT return a partial candle list marked as
  successful; it SHALL fail the request instead.

### Requirement: Stable errors

Invalid BFF parameters SHALL return HTTP 400 with the Research Service error
envelope. Market Data Service unavailability SHALL return HTTP 503. Other
Market Data Service contract failures SHALL be mapped through structured
upstream errors.

#### Scenario: Market Data Service is unreachable

- **WHEN** Market Data Service does not respond
- **THEN** the route returns HTTP 503 using the Research Service error
  envelope.

### Requirement: Clean architecture

The router and use case SHALL NOT import legacy BBB modules, SQLite, or
direct Market Data Service transport implementation details. The Market
Data Service adapter SHALL remain behind `MarketDataPort`.

#### Scenario: Layering check

- **WHEN** the candles-window router or use case module is inspected
- **THEN** it references only `MarketDataPort`, never an HTTP client or
  SQLite driver directly.
