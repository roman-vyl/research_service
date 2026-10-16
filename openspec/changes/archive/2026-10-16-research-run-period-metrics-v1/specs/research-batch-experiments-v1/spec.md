## ADDED Requirements

### Requirement: Period summary of a completed candidate

A completed candidate's row SHALL expose, computed from its own ordered closed-trade list:

- `period_split_ms`: the split instant used;
- `is_net_pnl` and `is_trades`: over the trades with `exit_time_ms < period_split_ms`;
- `oos_net_pnl` and `oos_trades`: over the other trades.

A part's net PnL SHALL be `initial_equity * (prod(1 + r) - 1)` over its trades in trade order, with the per-trade
return `r = net_pnl / equity_before`; a part without trades SHALL report net 0 and 0 trades. The split instant
SHALL be the request's `period_split_ms`, or 2023-07-01T00:00:00Z (1688169600000) when the request has none.

#### Scenario: Each part compounds from the initial equity

- **WHEN** a candidate with initial equity 10000 has trades with returns +10 % and -5 % before the split and +20 %
  after it
- **THEN** `is_net_pnl` is 450 (10000 * (1.1 * 0.95 - 1)), `is_trades` is 2, `oos_net_pnl` is 2000 and `oos_trades`
  is 1.

#### Scenario: Trade exiting at the split instant

- **WHEN** a trade's `exit_time_ms` equals `period_split_ms`
- **THEN** it belongs to the out-of-sample part.

#### Scenario: No trades

- **WHEN** a completed candidate has no realised trades
- **THEN** both parts report net 0 and 0 trades.

### Requirement: Yearly summary of a completed candidate

A completed candidate's row SHALL expose `years`, a map from the UTC calendar year of the trades' `exit_time_ms` to
`return_pct` and `trades`, with an entry only for years that have a trade. A year's `return_pct` SHALL be
`equity_after` of its last trade divided by `equity_before` of its first trade, minus 1. `years_up` SHALL be the
number of years with `return_pct > 0` and `worst_year` the smallest `return_pct`, null without trades.

#### Scenario: Year return over the account's own equity chain

- **WHEN** the first 2024 trade starts at equity 12000 and the last 2024 trade ends at 15000
- **THEN** `years["2024"].return_pct` is 0.25.

#### Scenario: Year without trades

- **WHEN** a candidate has trades in 2022 and 2024 only
- **THEN** `years` has entries 2022 and 2024 and no entry for 2023.

### Requirement: Trade averages of a completed candidate

A completed candidate's row SHALL expose `avg_trade_bp` = the mean per-trade return `r` times 10000, and
`payoff_ratio` = the mean `r` of trades with `r > 0` divided by minus the mean `r` of trades with `r < 0`.
`avg_trade_bp` SHALL be null without trades; `payoff_ratio` SHALL be null when there is no winning or no losing
trade.

#### Scenario: Payoff without losers

- **WHEN** every trade of a candidate has a positive return
- **THEN** `payoff_ratio` is null.

### Requirement: Summary fields of a failed candidate

A failed candidate SHALL NOT populate the period, yearly or trade-average fields. Summaries persisted before these
fields existed SHALL remain valid.

#### Scenario: Failed candidate

- **WHEN** a candidate fails
- **THEN** its row has no `period_split_ms`, `is_net_pnl`, `years`, `years_up`, `worst_year`, `avg_trade_bp` or
  `payoff_ratio`.
