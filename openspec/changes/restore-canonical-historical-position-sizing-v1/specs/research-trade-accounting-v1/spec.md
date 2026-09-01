## MODIFIED Requirements

### Requirement: Equity realisation

`AccountingPolicy.initial_equity` SHALL seed the candidate's current available realised equity. Entry fee SHALL be calculated from actual entry fill notional, participate in the all-in entry sizing budget, and be carried into closed-trade accounting. Exit fee SHALL be calculated only from actual exit fill notional at close. Each closed trade SHALL change equity by exactly its side-aware gross PnL less entry and exit fees, and the resulting equity SHALL be the sizing equity for the next position. An open position at range end SHALL not fabricate a realised equity update.

#### Scenario: Equity after a closed trade sizes the next entry

- **WHEN** a trade closes and its net PnL changes current equity
- **THEN** the next entry's quantity is calculated from that updated equity, not initial equity and not a fixed unit.

#### Scenario: Fees participate in compounding

- **WHEN** entry and exit fees reduce a closed trade's net PnL
- **THEN** the reduced `equity_after` is used to size the next position.

## ADDED Requirements

### Requirement: Financial state fails closed

The canonical lifecycle SHALL reject a candidate/run when initial/current equity, actual fill price, calculated quantity, fill notional, fee, PnL, or next equity is non-finite or when any value required to size a new position is non-positive. It SHALL also reject a broken equity chain. It SHALL NOT substitute quantity `1`, clip equity, skip fees, or publish partial success for that candidate.

#### Scenario: Loss exhausts available equity

- **WHEN** a closed trade produces non-positive next equity
- **THEN** the candidate fails before any later entry is sized
- **AND** no fallback quantity or successful accounting result is emitted.

#### Scenario: Equity chain mismatch

- **WHEN** a closed trade's `equity_before` differs from the lifecycle's current available equity
- **THEN** accounting fails closed rather than repairing or masking the mismatch.
