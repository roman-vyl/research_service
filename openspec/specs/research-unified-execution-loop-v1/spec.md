# Research Unified Execution Loop v1 Specification

## Purpose

Define the bar-by-bar execution loop that drives one strategy instance
through entries, exits, and position lifecycle for v1: execution facts and
events only, with fees/PnL/equity/metrics out of scope for this layer.
## Requirements
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

### Requirement: Position cardinality

The loop MUST maintain at most one open position for one strategy instance.
Partial exits, pyramiding, and cross-instance portfolio netting are out of
scope for v1.

#### Scenario: Second entry while a position is open

- **WHEN** a new entry decision fires while the instance already has an
  open position
- **THEN** the loop does not open a second, partial, or pyramided position.

### Requirement: Bar ordering

A position present at bar open MUST be evaluated for exit before any entry
decision on that bar.

#### Scenario: Exit and entry both eligible same bar

- **WHEN** a position open at bar start could exit and a new entry signal
  also fires on the same bar
- **THEN** the exit is evaluated first.

### Requirement: Entry-bar isolation

A position opened at the current bar close MUST NOT be evaluated for exit
on the same bar.

#### Scenario: Position opens at bar close

- **WHEN** a position opens at the close of bar N
- **THEN** it is not evaluated for exit until bar N+1.

### Requirement: Replacement-entry isolation

When a position existed at bar open, the loop MUST NOT open a replacement
position on that bar, even if the existing position closes.

#### Scenario: Position closes mid-bar

- **WHEN** a position open at bar start closes during bar N
- **THEN** no new position opens on bar N, even if an entry signal is also
  present.

### Requirement: Managed timing

Managed replay MUST be resolved once per opened position and MUST only
affect bars identified by `effective_from_time_ms`.

#### Scenario: Managed replay resolution

- **WHEN** a position opens
- **THEN** its managed replay is requested once, and each managed decision
  only takes effect starting at its own `effective_from_time_ms`.

### Requirement: End-of-range state

The loop MUST preserve an unclosed position as `open`; it MUST NOT create a
synthetic exit fill at the final candle.

#### Scenario: Position still open at range end

- **WHEN** the requested range ends while a position is still open
- **THEN** the loop reports it as `open`, with no synthetic exit fill
  created at the last candle.

### Requirement: Output boundary

The v1 result MUST contain execution facts and events only. Fees, PnL,
equity, and trade metrics MUST NOT be calculated in this slice.

#### Scenario: Loop output shape

- **WHEN** the loop result is inspected
- **THEN** it contains fills, position state, and events, with no fee, PnL,
  equity, or metric fields — those are produced by
  `research-trade-accounting-v1`.

### Requirement: Single-instance production wiring (I7)

`RunSingleInstanceBacktest` SHALL drive this execution loop from a real
`HistoricalExecutionProjectionDTO` obtained from Strategy Engine's live
`/strategy-evaluations/range` route (post I7 cutover), not from an
in-process proof harness. The batch path
(`application/experiments/run_batch.py`) SHALL continue to use its
existing legacy-shape execution path unmodified — this loop's I7 wiring
change applies to the single-instance production caller only. Full
cutover requirements (shared-infrastructure handling, compatibility,
rollback, E2E gate) are normative in `research-production-cutover-v1`;
this requirement records only that this loop itself is the thing being
wired to a real route for the first time.

#### Scenario: Single-instance run is driven by the real route

- **WHEN** a production `RunSingleInstanceBacktest.execute()` call runs
  after I7
- **THEN** this execution loop consumes a `HistoricalExecutionProjectionDTO`
  decoded from a real HTTP response of the live, cut-over `/range` route
- **AND** batch's use of this loop's legacy-shape counterpart is
  unaffected.

