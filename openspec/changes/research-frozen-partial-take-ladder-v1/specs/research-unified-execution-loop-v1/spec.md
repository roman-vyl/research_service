## MODIFIED Requirements

### Requirement: Position cardinality

The loop MUST maintain at most one open position for one strategy instance.
Pyramiding and cross-instance portfolio netting are out of scope for v1.
Partial exits MUST happen only through the frozen partial take ladder
(`research-partial-take-execution-v1`): such reductions shrink the one
open position and MUST NOT open, split, or replace a position.

#### Scenario: Second entry while a position is open

- **WHEN** a new entry decision fires while the instance already has an
  open position
- **THEN** the loop does not open a second, partial, or pyramided position.

#### Scenario: Entry decision while a reduced position is open

- **WHEN** a position has been reduced by a partial take and is still open
- **AND** a new entry decision fires
- **THEN** the loop does not open another position until the reduced
  position has closed.
