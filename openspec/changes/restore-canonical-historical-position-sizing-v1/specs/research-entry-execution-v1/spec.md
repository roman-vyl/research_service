## ADDED Requirements

### Requirement: Canonical equity-sized entry fill

For each canonical historical entry, Research SHALL first resolve the actual fill price using existing side-aware adverse entry slippage, then calculate a positive quantity as current available realised equity divided by that actual fill price, and finally record both values on `EntryFill`. `EntryDecision` SHALL remain free of equity and quantity.

#### Scenario: First long entry without slippage

- **WHEN** current available equity is `10000`, the actual entry fill price is `50000`, and entry slippage is zero
- **THEN** the recorded quantity is `0.2`.

#### Scenario: Long sizing uses slipped fill price

- **WHEN** a long entry has non-zero adverse entry slippage
- **THEN** Research increases the reference price by the configured slippage before dividing current equity by the resulting actual fill price.

#### Scenario: Short sizing uses slipped fill price

- **WHEN** a short entry has non-zero adverse entry slippage
- **THEN** Research decreases the reference price by the configured slippage before dividing current equity by the resulting actual fill price
- **AND** the recorded short quantity remains a positive magnitude.

#### Scenario: Fixed ExecutionPolicy quantity is unavailable

- **WHEN** a canonical historical entry is executed
- **THEN** its quantity is not copied from `ExecutionPolicy.quantity` and no canonical fixed-quantity branch is selected.
