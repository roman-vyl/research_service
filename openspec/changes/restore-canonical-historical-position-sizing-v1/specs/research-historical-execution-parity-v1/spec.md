## ADDED Requirements

### Requirement: Canonical position-sizing parity gate

Before production cutover, old-BBB/vectorbt-grounded historical parity evidence SHALL cover the restored full-current-equity sizing lifecycle rather than a fixed-unit substitute. The comparison SHALL include ordered entry quantity, actual entry and exit notionals, configured fees, side-aware gross/net PnL, `equity_before`, `equity_after`, and final equity across multiple sequential positions for both long and short.

#### Scenario: First-entry sizing baseline

- **WHEN** the parity fixture starts with equity `10000` and actual first entry fill price `50000` without slippage
- **THEN** both the independent reference and canonical Research path record quantity `0.2`.

#### Scenario: Prior trade changes later quantity

- **WHEN** a closed trade changes equity before a later entry
- **THEN** both paths size the later entry from identical updated equity and actual fill price
- **AND** exact Decimal quantity, notional, fee, PnL, and equity-chain facts match.

#### Scenario: Fixed-unit result cannot pass

- **WHEN** execution quantities remain fixed at `1` while reference equity or fill prices vary
- **THEN** the parity gate fails rather than accepting aggregate PnL coincidence.
