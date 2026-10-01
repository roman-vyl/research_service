## MODIFIED Requirements

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

## ADDED Requirements

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
