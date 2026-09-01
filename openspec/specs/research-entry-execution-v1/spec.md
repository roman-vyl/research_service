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

### Requirement: Canonical equity-sized entry fill

For each canonical historical entry, Research SHALL first resolve the actual fill price using existing side-aware adverse entry slippage, then calculate a positive quantity so actual entry notional plus proportional entry fee fit current available realised equity, and finally record both values on `EntryFill`. Under the existing no-fixed-fee assumptions, quantity SHALL equal `current_equity / (actual_entry_fill_price * (1 + entry_fee_rate))` for both long and short. `EntryDecision` SHALL remain free of equity and quantity.

#### Scenario: First long entry at zero fee

- **WHEN** current available equity is `10000`, the actual entry fill price is `50000`, and entry fee is zero
- **THEN** the recorded quantity is `0.2`.

#### Scenario: Long sizing uses slipped fill price

- **WHEN** a long entry has non-zero adverse entry slippage
- **THEN** Research increases the reference price by the configured slippage before applying the fee-aware sizing denominator.

#### Scenario: Short sizing uses slipped fill price

- **WHEN** a short entry has non-zero adverse entry slippage
- **THEN** Research decreases the reference price by the configured slippage before applying the fee-aware sizing denominator
- **AND** the recorded short quantity remains a positive magnitude.

#### Scenario: Entry fee fits inside the all-in budget

- **WHEN** either a long or short entry has a non-zero proportional entry fee
- **THEN** Research sizes quantity using `current_equity / (actual_entry_fill_price * (1 + entry_fee_rate))`
- **AND** entry notional plus entry fee equals current available equity within the canonical Decimal precision
- **AND** entry notional alone is less than current available equity.

#### Scenario: Fixed ExecutionPolicy quantity is unavailable

- **WHEN** a canonical historical entry is executed
- **THEN** its quantity is not copied from `ExecutionPolicy.quantity` and no canonical fixed-quantity branch is selected.
