## ADDED Requirements

### Requirement: Explicit ownership of three ranges

The architecture SHALL distinguish market availability, requested research
evaluation range, and Strategy Engine market-input/warmup range. No service
SHALL use the phrase or behavior "all data" without resolving it to explicit
half-open millisecond boundaries.

#### Scenario: A caller asks for "all data"

- **WHEN** a caller requests a full-history run
- **THEN** the request is resolved to an explicit half-open millisecond
  range before Strategy Engine evaluation begins, never left as an implicit
  "everything" request.

### Requirement: Market Data Service coverage

Market Data Service SHALL expose canonical stream coverage containing
ticker, timeframe, lifecycle state, inclusive available start, and
exclusive available end. The read SHALL be side-effect free and SHALL NOT
trigger audit, repair, or bootstrap.

#### Scenario: Coverage read for a ready stream

- **WHEN** Research Service reads coverage for a ready ticker/timeframe
  stream
- **THEN** it receives `available_from_ms` (inclusive) and
  `available_to_ms` (exclusive) from one consistent snapshot, and no audit
  or repair is triggered by the read.

### Requirement: Strategy-owned warmup

Strategy Engine SHALL derive required warmup from the validated strategy
spec and semantic feature plan. Callers SHALL NOT be required to calculate
indicator, HTF, lookback, or state-replay warmup.

#### Scenario: Caller does not supply warmup

- **WHEN** Research Service submits an evaluation range without any warmup
  calculation of its own
- **THEN** Strategy Engine derives the required warmup internally from the
  strategy spec and feature plan.

### Requirement: Separate input and output ranges

Strategy Engine MAY read candles before the requested evaluation start. It
SHALL return public features and decisions aligned to the requested
evaluation range while reporting the expanded market-input range in
metadata.

#### Scenario: Warmup extends before the evaluation start

- **WHEN** Strategy Engine needs candles before the requested evaluation
  start to warm up indicators
- **THEN** its response's public decision arrays are still aligned to the
  requested evaluation range, and the wider input range is reported
  separately in metadata.

### Requirement: History policy

Range evaluation SHALL support `require_fully_warmed` and
`allow_partial_warmup`. The former SHALL fail with structured
`insufficient_history` when the first requested bar cannot be fully
evaluated. The latter SHALL expose validity metadata and SHALL NOT emit
actionable decisions before validity.

#### Scenario: require_fully_warmed with insufficient history

- **WHEN** a `require_fully_warmed` request's first bar cannot have all
  required inputs valid
- **THEN** the request fails with structured `insufficient_history`.

#### Scenario: allow_partial_warmup before validity

- **WHEN** an `allow_partial_warmup` request's evaluation range starts
  before its `valid_from_ms`
- **THEN** decisions before `valid_from_ms` are not actionable, and the
  response's validity metadata reflects that.

### Requirement: Canonical origin and metadata

Indicator and strategy responses SHALL expose deterministic range,
validity, and provenance metadata sufficient to reproduce the calculation.
Research Service SHALL use coverage metadata to establish canonical
chart-indicator origins rather than the first arbitrary BFF request.

#### Scenario: EMA chart origin

- **WHEN** the EMA-window BFF establishes a chart's `calculation_origin_ms`
- **THEN** it uses Market Data Service coverage metadata rather than the
  first request's arbitrary range start.

### Requirement: Deferred coordinated implementation

The requirements in this change that depend on Strategy Engine or Market
Data Service behavior SHALL remain planned and unimplemented until those
services' matching halves exist, coordinated across all three services
rather than partially activated in only one. Research Service's own range
resolution and Market Data Service acquisition (`explicit_range` /
`full_available`, continuity audit, `market_data_hash` verification) are no
longer part of this deferred scope — they are current, implemented
Research Service behavior; see `research-single-instance-backtest-v1`.

#### Scenario: Partial single-service activation

- **WHEN** any one of the three services considers implementing a
  Strategy-Engine-warmup or Market-Data-Service-coverage-contract
  requirement from this change alone
- **THEN** it does not activate that behavior until the other services'
  matching halves are ready, per the coordinated rollout this change
  defines.
