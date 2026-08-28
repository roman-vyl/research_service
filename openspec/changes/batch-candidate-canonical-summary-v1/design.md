## Context

`RunBatchExperiment._settle_candidate` already produces, per candidate, a
fully materialized and persisted `SingleInstanceBacktestResult` before it
builds today's minimal `BatchCandidateResult`. The new fields below are
derived from the in-memory materialized result's `accounting.trades`,
immediately after successful persistence — not from the Engine
evaluation (`outcome`), and not by rereading the artifact from disk — so
no dense data crosses the batch-row boundary and the existing candidate
working-set release point is unaffected. Batch does not call
`RunSingleInstanceBacktest`; the canonical invariant this change relies
on is that both the standalone and batch paths go through
`MaterializeBacktestOutcome` → `PersistSingleInstanceBacktest`, with no
batch-specific execution or accounting logic.

## Metric definitions (normative)

All computed from `accounting.trades: tuple[TradeRecord, ...]` and
`accounting.initial_equity`, after materialize + persist, for one
candidate. `trade.net_pnl` is always net-of-fees.

- **`return_pct`** = `net_pnl / initial_equity`. Fraction, not
  percentage points. Zero net PnL → `0`.
- **`win_rate`** = `count(trade.net_pnl > 0) / realised_trade_count`.
  Break-even (`net_pnl == 0`) does not count as a winner. Zero trades →
  `null`.
- **`profit_factor`** = `sum(trade.net_pnl where > 0) / abs(sum(trade.net_pnl
  where < 0))`, using net PnL after fees. No losing trades → `null`
  (undefined, not infinite). Losses present but no winners → `0`.
- **`max_drawdown`** = `min(equity / running_peak - 1)` walked over the
  ordered closed-trade equity chain (`trade.equity_before` /
  `trade.equity_after` in trade order — trades already execute in a
  well-defined sequence per the existing execution loop). Fraction,
  negative-or-zero. No trades → `0`. This is trade-close equity drawdown,
  not a bar-level/mark-to-market drawdown — no bar-indexed equity series
  is computed or stored anywhere in the canonical result, and this change
  does not add one.
- **`BatchSideSummary`** (`long`, `short`): the same four formulas
  above (`trades`, `net_pnl`, `return_pct`, `win_rate`, `profit_factor`),
  computed over `trades` filtered to that `side`. `return_pct` for a side
  uses the same candidate-level `initial_equity` as denominator (there is
  no separate per-side equity base).

## Explicitly out of scope

- **Sharpe ratio.** The legacy system computed it two incompatible ways
  (`mean(pnl)/std(pnl)*sqrt(N)` on one execution path, a different
  vectorbt-based definition on another) — there is no single canonical
  formula to inherit, and this change does not invent one. Left for a
  future change if a specific definition is ever adopted as canonical.
- **Trade-quality counters** (`high_mfe_high_capture`,
  `stop_loss_after_low_mfe`, etc.). `TradeRecord.path` carries the raw
  per-trade MFE/MAE/capture/giveback numbers needed, but classifying them
  into buckets requires a threshold config
  (`high_mfe_atr`/`giveback_failure_atr`/...) that does not currently flow
  into the accounting/batch layer. Introducing that config surface is a
  separate concern from this change.
- **Exit-reason / profile breakdown, path-diagnostics percentiles.**
  These aggregates do not exist in the current persisted run or in any
  existing diagnostics projection — the canonical run retains raw
  per-trade facts only. Producing such breakdowns is outside this
  batch-summary change and, if ever needed, would be built by future or
  on-demand diagnostics work, not folded into a per-candidate index row.
- **Engine transport, `/range-batch` request/response shape.** Untouched.

## Where the row is built

`_settle_candidate` (`run_batch.py`) builds the row immediately after
`self._persist_backtest.execute(...)` succeeds, from the in-memory
`materialized.result.accounting.trades` and
`materialized.result.accounting.initial_equity` already in hand — no
disk reread, no additional Engine or storage call. On any exception
during materialize/persist, the existing `status="failed"` branch is
unchanged and none of the new fields are populated (they simply do not
exist on a failed candidate row, per the "row summarizes an
already-persisted run" invariant made explicit in the modified
requirement).
