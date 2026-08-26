# Research Market Chart Bundle v1 Specification

## Purpose

Define the preserved, deprecated chart-bundle BFF route that combines OHLCV
and a three-EMA overlay stack in one response.

## Requirements

### Requirement: Preserved, deprecated route

Research Service SHALL expose `GET /api/market/chart-bundle` with the legacy
Workbench request parameters and response structure. The route SHALL be
marked deprecated in the OpenAPI schema; it remains for existing Workbench
compatibility and is not the origin path for new consumers.

#### Scenario: OpenAPI schema

- **WHEN** the service's OpenAPI schema is generated
- **THEN** `GET /api/market/chart-bundle` is marked `deprecated: true`.

### Requirement: External data ownership

Research Service SHALL obtain OHLCV candles through `MarketDataPort` and EMA
values through `StrategyEnginePort`. Research Service SHALL NOT calculate
EMA values locally.

#### Scenario: Building the bundle

- **WHEN** a chart-bundle request is served
- **THEN** candles come from `MarketDataPort` and each EMA overlay comes
  from `StrategyEnginePort`, never a local EMA calculation.

### Requirement: Ordered overlays

The response SHALL contain exactly three overlays ordered as `fast`,
`anchor`, and `slow`, using the periods supplied in the request.

#### Scenario: Response overlay order

- **WHEN** a chart-bundle response is returned
- **THEN** its overlay list contains exactly `fast`, `anchor`, `slow` in
  that order, at the requested periods.

### Requirement: Validation

Requests SHALL be rejected when the periods do not satisfy
`fast < anchor < slow`.

#### Scenario: Out-of-order periods

- **WHEN** a request supplies periods where `fast >= anchor` or
  `anchor >= slow`
- **THEN** the route rejects the request with an `invalid_request` error.

### Requirement: Request efficiency

A chart-bundle request SHALL perform one Market Data Service range read. A
request MAY repeat candle reads on repeated identical requests but SHALL
reuse already materialized EMA ranges from the app-scoped EMA cache.

#### Scenario: Repeated identical request

- **WHEN** the same chart-bundle request is made again
- **THEN** the EMA overlays are served from the app-scoped EMA cache rather
  than re-requested from Strategy Engine in full.
