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
period. `cache_hit` SHALL be true only when the requested range is fully
covered by the existing cache entry and the request requires no Strategy
Engine call. A request that extends the right edge of a previously cached
window SHALL request only the missing suffix from Strategy Engine, reusing
the cached prefix, but SHALL report `cache_hit=false` — it still required an
upstream call.

#### Scenario: Cold miss

- **WHEN** no cache entry exists yet for the ticker/timeframe/period
- **THEN** the full requested range is fetched from Strategy Engine and
  `cache_hit` is `false`.

#### Scenario: Full cache hit

- **WHEN** a cache entry already covers the entire requested range
- **THEN** no Strategy Engine call is made and `cache_hit` is `true`.

#### Scenario: Right-edge extension is not a cache hit

- **WHEN** a cache entry covers only a prefix of the requested range
- **THEN** only the missing right-edge suffix is requested from Strategy
  Engine, the response combines the cached prefix with the fetched suffix,
  and `cache_hit` is `false`.

### Requirement: Honest origin metadata

Until an upstream earliest-available boundary exists, `calculation_origin_ms`
SHALL equal the first requested range start. The service SHALL NOT claim
full-history canonical origin parity.

#### Scenario: First request for a ticker/period

- **WHEN** no upstream earliest-available boundary is known yet
- **THEN** `calculation_origin_ms` in the response equals the start of the
  first requested range, not an assumed full-history origin.
