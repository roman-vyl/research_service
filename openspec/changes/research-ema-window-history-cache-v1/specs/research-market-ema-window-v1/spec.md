## MODIFIED Requirements

### Requirement: Cache behavior

The BFF SHALL retain a process-local authoritative cache keyed by ticker and timeframe. Its entry SHALL
hold the full committed history of the EMA periods 200, 500 and 1000 as compact numeric arrays, produced
by one Strategy Engine calculation over the history bounds served by Market Data Service. Independently
calculated pieces SHALL NOT be concatenated. `cache_hit` SHALL be true only when a request is answered
by slicing the authoritative entry without a Strategy Engine call. A request outside the entry's
coverage SHALL be answered with the part inside it and `truncated=true` and SHALL NOT trigger a
calculation.

#### Scenario: Authoritative cache ready

- **WHEN** the authoritative entry exists and a request lies inside its coverage
- **THEN** no Strategy Engine call is made, `cache_hit` is `true`, and the values do not depend on the
  order in which windows were requested.

#### Scenario: Scrolling to any earlier window

- **WHEN** a request starts before every earlier request of the process but inside the history
- **THEN** it is answered by a slice with points for the whole requested range.

#### Scenario: Request outside the history

- **WHEN** a request extends beyond the entry's coverage
- **THEN** the points inside the coverage are returned and `truncated` is `true`.

### Requirement: Honest origin metadata

`calculation_origin_ms` SHALL equal the start of the Strategy Engine calculation that produced the served
values. For the authoritative entry it SHALL equal the earliest committed bar reported by Market Data
Service stream bounds; for a preview it SHALL equal the start of the preview calculation, including its
warm-up. The service SHALL NOT claim run-specific or canonical-origin parity beyond that.

#### Scenario: Authoritative entry

- **WHEN** a response is served from the authoritative entry
- **THEN** `calculation_origin_ms` equals the earliest committed bar of the stream.

#### Scenario: Preview

- **WHEN** a response is served from a preview
- **THEN** `calculation_origin_ms` is the start of the preview calculation, earlier than the requested
  start by the warm-up.

## ADDED Requirements

### Requirement: Preview while the history is built

The first request for a ticker and timeframe SHALL start, once, a background build of the authoritative
entry and SHALL be answered, like every request until the build is published, by a preview: one Strategy
Engine calculation over the requested range preceded by a warm-up of five times the period in bars, served
from the requested start, with `cache_hit` `false`. Previews SHALL NOT be stored. The build SHALL be
published by one atomic replacement.

#### Scenario: First chart open

- **WHEN** the first EMA-window request of a process arrives
- **THEN** it is answered from a preview without waiting for the history build.

#### Scenario: Build in progress

- **WHEN** further requests arrive before the build is published
- **THEN** each is answered by a preview and no second build is started.

#### Scenario: Failed build

- **WHEN** the history build fails
- **THEN** previews keep answering and the next request starts a new attempt.

### Requirement: History bounds source

The history bounds of the authoritative entry SHALL be read from Market Data Service stream bounds
(`earliest_open_time_ms`, `latest_open_time_ms`); no separate setting SHALL define them.

#### Scenario: Bounds

- **WHEN** the authoritative entry is built
- **THEN** it covers `[earliest_open_time_ms, latest_open_time_ms + step)` of the stream.
