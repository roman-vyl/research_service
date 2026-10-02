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
For a position with partial take reductions, gross PnL SHALL be the sum
over every exit fill (each reduction and the closing fill) of its
side-aware price difference from the entry fill price times that fill's
quantity.

#### Scenario: Short position gross PnL

- **WHEN** a short position's entry price is higher than its exit price
- **THEN** gross PnL is positive, proportional to executed quantity.

#### Scenario: Long position with two reductions

- **WHEN** a long position enters at 100 with quantity 100, reduces 25 at
  101 and 25 at 103, and closes 50 at 108
- **THEN** gross PnL SHALL be 25×1 + 25×3 + 50×8 = 500.

### Requirement: Independent fee calculation

Entry and exit fees SHALL be calculated independently from actual fill
notionals. With partial take reductions, the exit fee SHALL be the sum of
each exit fill's notional times the exit fee rate, and the exit notional
SHALL be the sum of the exit fill notionals.

#### Scenario: Entry and exit fee basis

- **WHEN** a trade's fees are calculated
- **THEN** the entry fee uses the entry fill notional and the exit fee uses
  the exit fill notional, each independently.

#### Scenario: Exit fee over several fills

- **WHEN** a trade has two reductions and a closing fill
- **THEN** its exit fee SHALL equal the exit fee rate times the sum of the
  three fill notionals.

### Requirement: Net PnL

Net PnL SHALL equal gross PnL less all fees.

#### Scenario: Net PnL calculation

- **WHEN** a `TradeRecord` is built
- **THEN** its net PnL equals gross PnL minus entry fee minus exit fee.

### Requirement: Equity realisation

`AccountingPolicy.initial_equity` SHALL seed the candidate's current available realised equity. Entry fee SHALL be calculated from actual entry fill notional, participate in the all-in entry sizing budget, and be carried into closed-trade accounting. Exit fee SHALL be calculated only from actual exit fill notional at close. Each closed trade SHALL change equity by exactly its side-aware gross PnL less entry and exit fees, and the resulting equity SHALL be the sizing equity for the next position. An open position at range end SHALL not fabricate a realised equity update.

#### Scenario: Equity after a closed trade

- **WHEN** a trade closes
- **THEN** equity changes by exactly that trade's net PnL, and by nothing else.

#### Scenario: Equity after a closed trade sizes the next entry

- **WHEN** a trade closes and its net PnL changes current equity
- **THEN** the next entry's quantity is calculated from that updated equity, not initial equity and not a fixed unit.

#### Scenario: Fees participate in compounding

- **WHEN** entry and exit fees reduce a closed trade's net PnL
- **THEN** the reduced `equity_after` is used to size the next position.

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

### Requirement: Financial state fails closed

The canonical lifecycle SHALL reject a candidate/run when initial/current equity, actual fill price, calculated quantity, fill notional, fee, PnL, or next equity is non-finite or when any value required to size a new position is non-positive. It SHALL also reject a broken equity chain. It SHALL NOT substitute quantity `1`, clip equity, skip fees, or publish partial success for that candidate.

#### Scenario: Loss exhausts available equity

- **WHEN** a closed trade produces non-positive next equity
- **THEN** the candidate fails before any later entry is sized
- **AND** no fallback quantity or successful accounting result is emitted.

#### Scenario: Equity chain mismatch

- **WHEN** a closed trade's `equity_before` differs from the lifecycle's current available equity
- **THEN** accounting fails closed rather than repairing or masking the mismatch.

### Requirement: One trade record per strategic position

A closed position with partial take reductions SHALL produce exactly one
trade record:

- `quantity` SHALL be the initial quantity Q0;
- `exit_price`, the exit bar, time and exit attribution SHALL describe the
  closing fill;
- `average_exit_price` SHALL be the quantity-weighted mean of every exit
  fill;
- `exit_fills` SHALL list every exit fill in execution order, each with
  its kind (`partial_take` or `final`), `take_id`, bar, time, price,
  quantity, notional, fee and attribution.

The record SHALL fail validation unless the fill quantities sum to
`quantity`, the fill fees sum to `exit_fee`, and the fill notionals sum to
`exit_notional`. A trade without reductions SHALL keep an empty
`exit_fills` and no `average_exit_price`.

#### Scenario: Ledger of a laddered trade

- **WHEN** a position reduces 25 at 101 and 25 at 103 and closes 50 at 108
- **THEN** its record SHALL have `quantity` 100, `exit_price` 108,
  `average_exit_price` 105, and three `exit_fills`.

#### Scenario: Trade without reductions

- **WHEN** a position closes in a single fill
- **THEN** its record SHALL be identical to the record produced before
  this change.

### Requirement: R measured on the initial quantity

R SHALL keep its denominator frozen at entry: the initial risk amount is
`Q0 × |entry fill price − initial stop price|`. Gross and net R SHALL be
the trade's total gross and net PnL across all fills divided by that
amount.

#### Scenario: R of a laddered trade

- **WHEN** a long position enters at 100 with Q0 100 and an initial stop
  at 95, and its gross PnL over all fills is 500
- **THEN** its gross R SHALL be 500 / (100 × 5) = 1.

### Requirement: Capture metrics on the average exit price

MFE and MAE SHALL keep their window from the entry bar through the
closing bar. The realised capture, capture ratio and giveback SHALL use
the average exit price instead of the closing fill price.

#### Scenario: Capture after reductions

- **WHEN** a long trade enters at 100 and its average exit price is 105
- **THEN** its captured price SHALL be 5.

