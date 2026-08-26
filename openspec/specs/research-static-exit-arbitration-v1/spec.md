# Research Static Exit Arbitration v1 Specification

## Purpose

Define how Research Service arbitrates static (non-managed) exit candidates
— initial stop, initial take, and signal exit — for an open position.

## Requirements

### Requirement: Static policy ownership

Research Service SHALL consume Strategy Engine signal-exit decisions and
existing `InitialProtection` levels (ownership boundary:
`research-service-boundaries-v1`).

#### Scenario: Static candidates come from upstream state

- **WHEN** static exit candidates are collected for a bar
- **THEN** the signal-exit flag comes from Strategy Engine and the stop/take
  levels come from the position's existing `InitialProtection`, neither
  recomputed locally.

### Requirement: Bar-open eligibility

Static exits SHALL be evaluated only for positions that were open at the
start of the bar. The entry bar SHALL NOT close the newly opened position.

#### Scenario: Position opened this bar

- **WHEN** a position opens during the current bar
- **THEN** static exits are not evaluated against it until the next bar.

### Requirement: Distance fill semantics

A stop or take level crossed by the bar open SHALL fill at the open.
Otherwise an intrabar touch SHALL fill at the level.

#### Scenario: Gap through the stop level

- **WHEN** the bar open price is already beyond the stop level
- **THEN** the fill price is the bar open, not the stop level.

#### Scenario: Intrabar touch

- **WHEN** the bar open has not crossed the level but the bar's high/low
  range touches it
- **THEN** the fill price is exactly the level.

### Requirement: Signal fill semantics

A true aligned signal-exit decision SHALL create a candidate filled at the
current bar close.

#### Scenario: Signal exit fires

- **WHEN** Strategy Engine's signal-exit decision is true for the open
  side on the current bar
- **THEN** a signal-exit candidate is created, filled at that bar's close.

### Requirement: Deterministic same-bar priority

Policy `v1` SHALL select stop loss before take profit before signal and
SHALL retain losing candidates.

#### Scenario: Stop and take both eligible on the same bar

- **WHEN** both a stop-loss candidate and a take-profit candidate are
  eligible on the same bar
- **THEN** the stop-loss candidate wins and the take-profit candidate is
  retained as a losing candidate in the arbitration trace.
