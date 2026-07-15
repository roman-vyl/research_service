# Specification: Research History Window Planning v1

## Requirement: Explicit ownership of three ranges

The architecture SHALL distinguish market availability, requested research evaluation range, and Strategy Engine market-input/warmup range. No service SHALL use the phrase or behavior “all data” without resolving it to explicit half-open millisecond boundaries.

## Requirement: Market Data Service coverage

Market Data Service SHALL expose canonical stream coverage containing ticker, timeframe, lifecycle state, inclusive available start and exclusive available end. The read SHALL be side-effect free and SHALL NOT trigger audit, repair or bootstrap.

## Requirement: Research range policy

Research Service SHALL own selection of the requested evaluation range. A `full_available` policy SHALL be resolved through Market Data Service coverage before Strategy Engine evaluation begins.

## Requirement: Strategy-owned warmup

Strategy Engine SHALL derive required warmup from the validated strategy spec and semantic FeaturePlan. Callers SHALL NOT be required to calculate indicator, HTF, lookback or state-replay warmup.

## Requirement: Separate input and output ranges

Strategy Engine MAY read candles before the requested evaluation start. It SHALL return public features and decisions aligned to the requested evaluation range while reporting the expanded market-input range in metadata.

## Requirement: History policy

Range evaluation SHALL support `require_fully_warmed` and `allow_partial_warmup`. The former SHALL fail with structured `insufficient_history` when the first requested bar cannot be fully evaluated. The latter SHALL expose validity metadata and SHALL NOT emit actionable decisions before validity.

## Requirement: Canonical origin and metadata

Indicator and strategy responses SHALL expose deterministic range, validity and provenance metadata sufficient to reproduce the calculation. Research Service SHALL use coverage metadata to establish canonical chart-indicator origins rather than the first arbitrary BFF request.

## Requirement: Deferred coordinated implementation

This specification SHALL remain planned and unimplemented until the current Research Service BFF and backend cutover reaches its final integration phases. Implementation SHALL be coordinated across Market Data Service, Strategy Engine and Research Service rather than partially activated in only one service.
