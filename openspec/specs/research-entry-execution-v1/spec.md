# Research Entry Execution v1 Specification

## Purpose

Define how Research Service turns a Strategy Engine entry decision into an
executed entry fill.

## Requirements

### Requirement: Aligned decisions

Entry execution SHALL consume only a `StrategyEvaluationResult` and
`MarketFrame` that describe the same canonical bar grid.

#### Scenario: Misaligned inputs

- **WHEN** the strategy evaluation and market frame describe different bar
  grids
- **THEN** entry execution SHALL NOT run against them (see the alignment
  invariant in `research-service-boundaries-v1`).

### Requirement: Legacy-compatible signal semantics

When both long and short entry decisions are true on a flat bar, long SHALL
win. The reference entry price SHALL be the signal bar close.

#### Scenario: Simultaneous long and short signal

- **WHEN** both sides signal entry on the same flat bar
- **THEN** the long entry is taken and the short signal is discarded for
  that bar.

### Requirement: Ready entry policy

An entry decision SHALL be executable only when the same side is ready
according to Strategy Engine `stop_ready`.

#### Scenario: Entry without a ready stop

- **WHEN** a side's entry decision is true but its `stop_ready` is false on
  the same bar
- **THEN** no entry is executed for that side on that bar.

### Requirement: One open position

An open position for an instance SHALL block subsequent entry decisions
until a later execution change closes it.

#### Scenario: Entry signal while already in position

- **WHEN** an instance already has an open position and a new entry
  decision fires
- **THEN** the new entry is not executed while the existing position
  remains open.
