## MODIFIED Requirements

### Requirement: Cache behavior

The BFF SHALL retain a process-local authoritative cache keyed by ticker and timeframe. Its entry SHALL
hold the full committed history of the EMA periods 200, 500 and 1000 as compact numeric arrays, produced
by one Strategy Engine calculation over the history bounds served by Market Data Service. Independently
calculated pieces SHALL NOT be concatenated. `cache_hit` SHALL be true when a request is fully answered
by slicing an existing preview or authoritative entry without a Strategy Engine call. It SHALL describe
whether the current request reused an existing calculation, not whether the entry is preview or
authoritative. The request whose Strategy Engine calculation creates the preview SHALL have
`cache_hit=false`; a later fully covered slice from that preview SHALL have `cache_hit=true`. `truncated`
SHALL remain a separate indication of requested-range coverage. A request outside the current entry's
coverage SHALL be answered with the part inside it and `truncated=true` and SHALL NOT trigger a
calculation or expansion.

#### Scenario: Cold miss

- **WHEN** no entry exists yet for the ticker and timeframe
- **THEN** one Strategy Engine call creates the multi-EMA preview, the authoritative build starts once in
  the background, and `cache_hit` is `false`.

#### Scenario: Full cache hit

- **WHEN** an existing preview or authoritative entry fully covers the requested range and period
- **THEN** no Strategy Engine call is made and `cache_hit` is `true`.

#### Scenario: Right-edge extension is not a cache hit

- **WHEN** an existing preview or authoritative entry covers only a prefix of the requested range
- **THEN** the available slice is returned with `truncated=true` and `cache_hit=false`, without a
  Strategy Engine call, concatenation, recalculation, or expansion.

#### Scenario: Authoritative cache ready

- **WHEN** the authoritative entry exists and a request lies inside its coverage
- **THEN** no Strategy Engine call is made, `cache_hit` is `true`, and the values do not depend on the
  order in which windows were requested.

#### Scenario: Preview creation is not a cache hit

- **WHEN** a request performs the Strategy Engine calculation that creates the preview entry
- **THEN** `cache_hit` is `false`.

#### Scenario: Existing preview entry

- **WHEN** an existing preview entry fully covers a request for a supported EMA period
- **THEN** no Strategy Engine call is made and `cache_hit` is `true`.

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

#### Scenario: First request for a ticker/period

- **WHEN** the first request is served from the newly calculated preview
- **THEN** `calculation_origin_ms` is the start of that preview calculation, including its warm-up, rather
  than the requested range start.

## ADDED Requirements

### Requirement: Preview while the history is built

The first request for a ticker and timeframe SHALL start, once, a background build of the authoritative
entry and SHALL create one temporary preview entry for EMA 200, 500 and 1000 with one Strategy Engine
calculation. The preview calculation SHALL cover the requested range preceded by a warm-up of five times
the maximum period, 5 000 bars. The triggering request SHALL be served from the requested start with
`cache_hit=false`; further fully covered requests for any of the three periods SHALL be slices of that
same preview with `cache_hit=true` and no Strategy Engine call. The preview SHALL have fixed coverage and
SHALL NOT expand. The full entry SHALL be published by one atomic replacement of the preview. The only
states for the supported stack SHALL be `EMPTY`, `PREVIEW` and `FULL`.

#### Scenario: First chart open

- **WHEN** the first EMA-window request of a process arrives
- **THEN** one Strategy Engine call calculates EMA 200, 500 and 1000 with a 5 000-bar warm-up, and the
  requested period is answered from that preview without waiting for the history build.

#### Scenario: Other stack periods while build is in progress

- **WHEN** fully covered requests for the other supported periods arrive before the full build is published
- **THEN** they are sliced from the same preview entry with `cache_hit=true`; no further preview call and
  no second full build is started.

#### Scenario: Window outside preview coverage

- **WHEN** a request arrives before the full build is published and extends outside the fixed preview
  coverage
- **THEN** the available slice is returned with `truncated=true` and the preview is not expanded or
  recalculated.

#### Scenario: Failed build

- **WHEN** the history build fails
- **THEN** the preview remains available and the next request starts a new full-build attempt.

### Requirement: History bounds source

The history bounds of the authoritative entry SHALL be read from Market Data Service stream bounds
(`earliest_open_time_ms`, `latest_open_time_ms`); no separate setting SHALL define them.

#### Scenario: Bounds

- **WHEN** the authoritative entry is built
- **THEN** it covers `[earliest_open_time_ms, latest_open_time_ms + step)` of the stream.
