# Research Unified Exit Arbitration v1 Specification

## Purpose

Define how Research Service arbitrates static and managed exit candidates
together into one winning `ExitFill` per bar.

## Requirements

### Requirement: One candidate pipeline

Research Service MUST arbitrate static and managed candidates together for
each executable bar.

#### Scenario: Both candidate kinds eligible

- **WHEN** a bar has both a static candidate (e.g. initial stop) and a
  managed candidate (e.g. managed stop) eligible
- **THEN** both are arbitrated in the same pipeline, not resolved
  independently.

### Requirement: Priority

The v1 order MUST be stop loss, managed stop, take profit, runtime
protective, runtime take, runtime close/runtime exit, then signal.

#### Scenario: Stop loss and managed stop both eligible

- **WHEN** both a static stop loss and a managed stop are eligible on the
  same bar
- **THEN** the static stop loss wins.

### Requirement: Active take profile

`disable_initial_tp` MUST suppress only the initial fixed take-profit
candidate. It MUST NOT suppress stop, managed stop, runtime take, or signal
candidates.

#### Scenario: disable_initial_tp is set

- **WHEN** the active exit profile sets `disable_initial_tp`
- **THEN** the initial fixed take-profit candidate is excluded from
  arbitration, while stop, managed stop, runtime take, and signal
  candidates remain eligible.

### Requirement: Bar identity

Candidates from different bar indices or timestamps MUST NOT be arbitrated
together.

#### Scenario: Candidates from different bars

- **WHEN** a static candidate for bar N and a managed candidate for bar N+1
  are both present
- **THEN** they are never compared in the same arbitration.

### Requirement: Attribution

The selected `ExitFill` MUST preserve the winning candidate layer, rule ID,
component ID, and exit kind when present.

#### Scenario: Winning candidate carries identity

- **WHEN** a managed candidate with a rule ID wins arbitration
- **THEN** the resulting `ExitFill` carries that rule ID and its layer
  (managed) and exit kind.
