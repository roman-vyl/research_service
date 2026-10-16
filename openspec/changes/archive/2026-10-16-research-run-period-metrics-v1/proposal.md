## Why

Most research surfaces (41 to 45 of 54) carry period metrics next to the run totals: net PnL in sample and out of
sample, the return of each calendar year, the number of profitable years and the worst year. Five or six surfaces
also carry the average trade in basis points and the payoff ratio. The research replay computes all of them from
the trade list. The batch summary of a Research run has only the totals, so Calculate refuses such a surface with
`unbound_metric`: a row calculated by the Engine could not fill those columns.

The owner chose to compute these metrics in Research, from the run's own trades, so that every cell of a calculated
row has one source (owner 2026-10-16: "Считать в ресерч"; metrics agreed the same day: IS / OOS, yearly return,
years up, worst year, average trade and payoff).

## What Changes

- The batch candidate summary of a completed candidate gains:
  - `is_net_pnl`, `oos_net_pnl`, `is_trades`, `oos_trades` and `period_split_ms`: trades split by exit time at the
    split instant, each part compounded again from the initial equity;
  - `years`: per calendar year (UTC) of the exit time, `return_pct` and `trades`;
  - `years_up` and `worst_year`;
  - `avg_trade_bp` and `payoff_ratio`, from the per-trade return on the equity before the trade.
- The split instant is `period_split_ms` of the batch request, default 2023-07-01T00:00:00Z. A manifest
  `materialize.research_policy` may set `period_split_ms`; Calculate passes it to the batch.
- Calculate result bindings can now name these fields (`is_net_pnl`, `years.2024.return_pct`, `years_up`, ...).
- No change to Strategy Engine, to accounting or to existing summary fields. Summaries written before this change
  stay valid (the new fields are optional).

## Out of scope

- `blocked_share` (needs the unfiltered signal count, which one run does not have): it stays a replay-only column;
  surfaces that carry it remain `unbound_metric` until their manifest drops it from the metrics or a later change.
- Surface-specific comparison metrics (`net_vs_tp55`, `return_2020_22`, ...).
- Manifest updates of the research data (result bindings, a per-row provenance column): done in the research data,
  not in this repository.
