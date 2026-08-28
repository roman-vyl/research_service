## MODIFIED Requirements

### Requirement: Aligned inputs

The execution loop MUST reject Strategy Engine and Market Data Service
inputs whose market identity, `market_data_hash`, `bar_count`, or
declared range differ. Every decision event's `bar_index` MUST fall
within `[0, bar_count)` for the aligned range; the loop MUST reject an
evaluation containing a `bar_index` outside that range. (Strategy
Engine no longer sends a per-bar timestamp array — `bar_index` plus
`market_data_hash` plus `bar_count` is the alignment contract; the
loop's own `MarketFrame` for that identical `market_data_hash` is the
sole source of each bar's actual timestamp.)

#### Scenario: Misaligned market identity

- **WHEN** the Strategy Engine and MDS inputs to the loop describe
  different market identity, `market_data_hash`, `bar_count`, or range
- **THEN** the loop rejects the run rather than executing against
  mismatched data.

#### Scenario: Out-of-range bar_index is rejected

- **WHEN** a decision event's `bar_index` falls outside `[0, bar_count)`
  for the aligned range
- **THEN** the loop rejects the run rather than executing against an
  ambiguous or out-of-bounds decision.
