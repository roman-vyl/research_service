# Research Trade Accounting v1 Specification

## Purpose

Define Research-owned realised accounting built on top of the execution
loop's `PositionExecution` items.

## Requirements

### Requirement: Closed positions only

Only closed `PositionExecution` items SHALL produce `TradeRecord` objects.

#### Scenario: Open position at accounting time

- **WHEN** accounting runs over a set of positions that includes one still
  open
- **THEN** no `TradeRecord` is produced for the open position.

### Requirement: Side-aware gross PnL

Gross PnL SHALL be side-aware and SHALL be multiplied by executed quantity.

#### Scenario: Short position gross PnL

- **WHEN** a short position's entry price is higher than its exit price
- **THEN** gross PnL is positive, proportional to executed quantity.

### Requirement: Independent fee calculation

Entry and exit fees SHALL be calculated independently from actual fill
notionals.

#### Scenario: Entry and exit fee basis

- **WHEN** a trade's fees are calculated
- **THEN** the entry fee uses the entry fill notional and the exit fee uses
  the exit fill notional, each independently.

### Requirement: Net PnL

Net PnL SHALL equal gross PnL less all fees.

#### Scenario: Net PnL calculation

- **WHEN** a `TradeRecord` is built
- **THEN** its net PnL equals gross PnL minus entry fee minus exit fee.

### Requirement: Equity realisation

Equity SHALL change only by realised net PnL.

#### Scenario: Equity after a closed trade

- **WHEN** a trade closes
- **THEN** equity changes by exactly that trade's net PnL, and by nothing
  else.

### Requirement: MFE/MAE window

MFE and MAE SHALL use candle high/low from entry through exit, inclusive.

#### Scenario: MFE/MAE calculation window

- **WHEN** MFE/MAE is calculated for a closed trade
- **THEN** the candle range used spans from the entry bar through the exit
  bar, both included.

### Requirement: Open positions reported, not forced

Open positions at range end SHALL be reported but SHALL NOT be
force-closed.

#### Scenario: Accounting an open position

- **WHEN** accounting runs over a position still open at range end
- **THEN** it is reported as open with no synthetic exit and no realised
  PnL.
