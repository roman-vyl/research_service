## ADDED Requirements

### Requirement: Canonical position-sizing parity gate

Before production cutover, old-BBB/vectorbt-grounded historical parity evidence SHALL cover the restored full-current-equity sizing lifecycle rather than a fixed-unit substitute. The comparison SHALL include ordered entry quantity, actual entry and exit notionals, configured fees, side-aware gross/net PnL, `equity_before`, `equity_after`, and final equity across multiple sequential positions for both long and short.

#### Scenario: First-entry sizing baseline

- **WHEN** the parity fixture starts with equity `10000`, actual first entry fill price `50000`, and zero entry fee
- **THEN** both the independent reference and canonical Research path record quantity `0.2`.

#### Scenario: Non-zero-fee parity on both sides

- **WHEN** independent long and short fixtures use non-zero proportional entry and exit fees
- **THEN** both the old-BBB/vectorbt-grounded reference and canonical Research path size entry quantity from `equity / (actual_entry_fill_price * (1 + entry_fee_rate))`
- **AND** entry notional, entry fee, exit fee, gross/net PnL, and next equity match for each side
- **AND** exit fee is derived only from the actual exit fill and does not alter entry quantity.

#### Scenario: Prior trade changes later quantity

- **WHEN** a closed trade changes equity before a later entry
- **THEN** both paths size the later entry from identical updated equity and actual fill price
- **AND** exact Decimal quantity, notional, fee, PnL, and equity-chain facts match.

#### Scenario: Fixed-unit result cannot pass

- **WHEN** execution quantities remain fixed at `1` while reference equity or fill prices vary
- **THEN** the parity gate fails rather than accepting aggregate PnL coincidence.
