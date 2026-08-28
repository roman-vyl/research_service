## MODIFIED Requirements

### Requirement: Aligned inputs

The execution loop MUST reject Strategy Engine and Market Data Service
inputs whose market identity, `market_data_hash`, `bar_count`, or
declared range differ. Every projection element's `bar_index` MUST fall
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

- **WHEN** a projection element's `bar_index` falls outside `[0, bar_count)`
  for the aligned range
- **THEN** the loop rejects the run rather than executing against an
  ambiguous or out-of-bounds decision.

## ADDED Requirements

### Requirement: Locked exit profile

At entry fill, the loop SHALL capture the entry opportunity's
`locked_exit_profile` value onto the resulting position and hold it
fixed for that position's entire life. Every subsequent bar the position
remains open, signal-exit and protection candidate lookups SHALL be
keyed by the position's own `locked_exit_profile` — never by whichever
exit profile is active on the current bar.

#### Scenario: Locked profile survives a later profile change

- **WHEN** a position enters under one exit profile and the market's
  current exit profile changes on a later bar while that position
  remains open
- **THEN** signal-exit and protection candidate lookups for that
  position continue to use the profile locked at entry, not the
  now-current profile.

#### Scenario: Locked profile is captured once, at fill

- **WHEN** a position is opened
- **THEN** its `locked_exit_profile` is set once, from the matching
  entry opportunity's value at fill time
- **AND** it is never reassigned for the life of that position.

### Requirement: Exit attribution restoration

Realised trade and execution-event records SHALL carry
`exit_reason`/`exit_rule_id`/`exit_component_id`/`exit_kind`/
`exit_layer` attribution sourced from Strategy Engine's attributed
initial-protection and signal-exit-candidate data — not a coarse
category synthesized independently of that attribution. Where multiple
applicable rules were aggregated into a single reported ratio at entry,
the attribution SHALL reflect the same deterministic rule selection
Strategy Engine's projection used.

#### Scenario: Exit attribution matches Engine's projection attribution

- **WHEN** a position closes
- **THEN** its trade record's exit attribution fields match the
  `rule_id`/`component_id`/`exit_kind` Strategy Engine's projection
  reported for the specific initial-protection or signal-exit candidate
  that triggered the exit.

#### Scenario: Attribution is not degraded to an always-on-only category

- **WHEN** a trade exits under a locked profile other than a default/
  always-on rule set
- **THEN** its attribution reflects that specific profile's rule/
  component, not a generic always-on category.
