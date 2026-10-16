## ADDED Requirements

### Requirement: Profit factor in R and entry signal count

A completed candidate's row SHALL expose:

- `profit_factor_r`: the sum of `net_r_multiple` over R-eligible trades with a positive net R divided by minus the
  sum over those with a negative net R; null when no R-eligible trade has a negative net R;
- `entry_signal_count`: the number of entry opportunities of the candidate's strategy evaluation.

A failed candidate SHALL NOT populate them.

#### Scenario: Profit factor in R

- **WHEN** a candidate's trades have net R of +3, -1 and -1
- **THEN** `profit_factor_r` is 1.5.

#### Scenario: No losing trade

- **WHEN** every R-eligible trade has a positive net R
- **THEN** `profit_factor_r` is null.
