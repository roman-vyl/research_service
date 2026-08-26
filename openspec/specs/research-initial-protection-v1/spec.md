# Research Initial Protection v1 Specification

## Purpose

Define how Research Service derives initial stop/take price levels for a
newly opened position from Strategy Engine's ratios.

## Requirements

### Requirement: Readiness-gated entry

A side SHALL be executable only when both its Strategy Engine entry
decision and its `stop_ready` value are true on the same aligned bar.

#### Scenario: Entry decision without readiness

- **WHEN** an entry decision is true but `stop_ready` is false on the same
  bar
- **THEN** the side is not executable on that bar.

### Requirement: Authoritative ratios

Research Service SHALL consume `stop_loss_ratio` and `take_profit_ratio`
from Strategy Engine (ownership boundary: `research-service-boundaries-v1`).

#### Scenario: Deriving initial levels

- **WHEN** a position opens
- **THEN** its initial stop and take prices are derived from Strategy
  Engine's `stop_loss_ratio`/`take_profit_ratio` for that side and bar, not
  from a locally computed value.

### Requirement: Legacy-compatible anchor

Under compatibility profile `bbb_v1`, initial stop/take prices SHALL be
anchored to the signal-bar close, even when explicit execution slippage
changes the entry fill price.

#### Scenario: Slippage on entry fill

- **WHEN** the entry fill price differs from the signal-bar close due to
  configured slippage
- **THEN** the initial stop/take levels are still anchored to the
  signal-bar close, not the slipped fill price.

### Requirement: Side-aware levels

Long and short stop/take levels SHALL use the reviewed legacy formulas and
SHALL reject invalid non-positive prices.

#### Scenario: Non-positive derived price

- **WHEN** a derived stop or take price would be zero or negative
- **THEN** `InitialProtection` for that side/bar is rejected rather than
  produced.
