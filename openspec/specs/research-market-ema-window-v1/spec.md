# Research Market EMA Window v1 Specification

## Purpose

Define the preserved Workbench EMA-window BFF route backed by Strategy
Engine's indicator evaluation API.

## Requirements

### Requirement: Preserved Workbench route

Research Service SHALL serve `GET /api/market/ema-window` with the existing
BBB query parameters and response field names.

#### Scenario: Workbench requests an EMA window

- **WHEN** the Workbench frontend calls `GET /api/market/ema-window`
- **THEN** the response uses the existing field names it always has.

### Requirement: Strategy Engine ownership

Research Service SHALL NOT calculate EMA locally. It SHALL request an EMA
feature through Strategy Engine `POST /v1/indicator-evaluations/range`.

#### Scenario: EMA value is needed

- **WHEN** the route needs an EMA series for the requested window
- **THEN** it requests it from Strategy Engine rather than computing it
  in-process.

### Requirement: Presentation conversion

Strategy Engine Decimal-text values SHALL be converted to JSON numbers only
at the BFF chart DTO boundary. Timestamps SHALL be converted from
milliseconds to Unix seconds.

#### Scenario: Response serialization

- **WHEN** the EMA-window response is built
- **THEN** Decimal-text values become JSON numbers and millisecond
  timestamps become Unix seconds only in that final conversion step.

### Requirement: Cache behavior

The BFF SHALL retain a process-local cache keyed by ticker, timeframe, and
period, report `cache_hit`, and request only a missing right-edge suffix
when extending cached coverage.

#### Scenario: Extending a cached window

- **WHEN** a later request extends the right edge of a previously cached
  ticker/timeframe/period window
- **THEN** only the missing suffix is requested from Strategy Engine and
  `cache_hit` reflects whether any cached data was reused.

### Requirement: Honest origin metadata

Until an upstream earliest-available boundary exists, `calculation_origin_ms`
SHALL equal the first requested range start. The service SHALL NOT claim
full-history canonical origin parity.

#### Scenario: First request for a ticker/period

- **WHEN** no upstream earliest-available boundary is known yet
- **THEN** `calculation_origin_ms` in the response equals the start of the
  first requested range, not an assumed full-history origin.
