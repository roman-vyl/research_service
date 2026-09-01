## ADDED Requirements

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
