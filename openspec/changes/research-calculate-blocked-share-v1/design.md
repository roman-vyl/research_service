## Context

The research replay computes `blocked_share = 1 - kept / signals`, `signals` = the cell's entry signals without the
filter, `kept` = those the filter lets through, before the one-position rule. The Engine's entry opportunities of a
spec are exactly the signals that pass every setup of that spec (vote parity on the Mac: Engine entries equal the
replica signals minus the blocked set in 54 of 54 cells), so the two counts are the entry-opportunity counts of the
row's spec and of the same spec without the filter. The replay profit factor is `sum(net R > 0) / -sum(net R < 0)`
over the trades; Research already has `net_r_multiple` per trade, and cumulative net R already passes parity.

## Decisions

- D1 `entry_signal_count` = `len(strategy_evaluation.entry_opportunities)` of the candidate's materialized run.
- D2 The base spec of a row is the materialized template with the row's `bindings` and no option item. It is
  validated by the Engine like any spec (its `config_hash` is kept in the plan). Rows with the same base share one
  base candidate (by canonical raw spec).
- D3 A batch call carries at most `BATCH_SIZE` candidates, rows and bases together; a chunk of rows is cut so that
  its rows and their distinct bases fit.
- D4 A row whose base failed (Engine error) settles `engine_failed` with the base's message; it is not published.
- D5 `blocked_share` is injected into the row's summary values under that name before result bindings are read, so
  the existing parity gate and publish path apply unchanged.
- D6 `profit_factor_r` uses only R-eligible trades (`net_r_multiple` not null), like `cumulative_net_r`; null when
  no eligible trade has a negative net R.
