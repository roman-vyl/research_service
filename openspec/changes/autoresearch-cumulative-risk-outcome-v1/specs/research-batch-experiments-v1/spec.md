## MODIFIED Requirements

### Requirement: Batch output shape

Batch output MUST retain candidate order and expose completed/failed
counts. A successful candidate's row MUST additionally expose derived
research-comparison metrics computed from that candidate's own
in-memory materialized canonical result, immediately after successful
persistence and with no disk reread, so candidates can be compared
without opening each full run artifact individually.

#### Scenario: Batch summary contents

- **WHEN** a batch completes
- **THEN** its summary lists candidates in request order and reports how
  many completed versus failed.

#### Scenario: Successful candidate row fields

- **WHEN** a candidate completes successfully
- **THEN** its row includes, in addition to the existing accounting
  totals (`realised_trade_count`, `open_position_count`, `final_equity`,
  `gross_pnl`, `fees_paid`, `net_pnl`, `market_data_hash`):
  `return_pct`, `win_rate` (nullable), `profit_factor` (nullable),
  `max_drawdown`, `cumulative_risk_outcome`, `long` (`BatchSideSummary`),
  `short` (`BatchSideSummary`).

#### Scenario: return_pct is a fraction of initial equity

- **WHEN** a successful candidate's `return_pct` is computed
- **THEN** it equals `net_pnl / initial_equity` as a fraction (not
  percentage points), and a candidate with zero net PnL reports `0`.

#### Scenario: win_rate excludes break-even trades and is null with no trades

- **WHEN** a successful candidate's `win_rate` is computed
- **THEN** it equals `count(trade.net_pnl > 0) / realised_trade_count`,
  a trade with `net_pnl == 0` does not count as a winner, and a
  candidate with zero realised trades reports `win_rate: null`.

#### Scenario: profit_factor uses net PnL and is null without losing trades

- **WHEN** a successful candidate's `profit_factor` is computed
- **THEN** it equals `sum(trade.net_pnl where > 0) /
  abs(sum(trade.net_pnl where < 0))` using net PnL after fees; a
  candidate with no losing trades reports `profit_factor: null`; a
  candidate with losing trades but no winning trades reports
  `profit_factor: 0`.

#### Scenario: max_drawdown is trade-close equity drawdown

- **WHEN** a successful candidate's `max_drawdown` is computed
- **THEN** it equals `min(equity / running_peak - 1)` walked over the
  candidate's ordered closed-trade equity chain
  (`trade.equity_before`/`trade.equity_after` in trade order), is a
  fraction that is negative or zero, is `0` for a candidate with zero
  realised trades, and is explicitly a trade-close metric — not a
  bar-level or mark-to-market drawdown.

#### Scenario: cumulative_risk_outcome is the R-multiple win/loss balance

- **WHEN** a successful candidate's (or one of its sides') `cumulative_risk_outcome`
  (ΣR) is computed
- **THEN** it equals `Decimal(N) * (2 * WR - 1)`, where `N` is that
  scope's realised trade count and `WR` is that scope's `win_rate`,
  computed directly from the same win/loss counts already used for
  `win_rate` (never by rounding `N * WR` back into an integer win
  count); a scope with zero realised trades reports
  `cumulative_risk_outcome: 0` even though its `win_rate` is `null`; and
  the aggregate value equals the sum of the `long` and `short` values by
  construction, since trades partition exactly into the two sides.

#### Scenario: long/short summaries use the same formulas per side

- **WHEN** a successful candidate's `long` and `short` summaries are
  computed
- **THEN** each equals `return_pct`/`win_rate`/`profit_factor`/`net_pnl`/
  `cumulative_risk_outcome` computed with the same formulas above,
  restricted to that candidate's trades with matching `side`, using the
  candidate's own `initial_equity` as the `return_pct` denominator for
  both sides.

#### Scenario: Sharpe and trade-quality counters are not included

- **WHEN** a successful candidate's row is inspected
- **THEN** it does not include a Sharpe ratio, trade-quality counters
  (e.g. high-MFE-capture or stop-loss-after-low-MFE counts), or any
  exit-reason/profile breakdown — none of these aggregates exist in the
  current persisted run artifact (which retains raw per-trade facts
  only), and producing them is outside this batch-summary change.

### Requirement: BatchSideSummary shape

A `BatchSideSummary` (used for a successful candidate's `long` and
`short` fields) SHALL contain exactly: `trades` (count), `net_pnl`,
`return_pct`, `win_rate` (nullable), `profit_factor` (nullable),
`cumulative_risk_outcome` — no dense or per-trade data.

#### Scenario: Side with zero trades

- **WHEN** a candidate has zero trades on one side
- **THEN** that side's summary reports `trades: 0`, `net_pnl: 0`,
  `return_pct: 0`, `win_rate: null`, `profit_factor: null`,
  `cumulative_risk_outcome: 0`.
