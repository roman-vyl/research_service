# Research Batch Experiments v1 Specification

## Purpose

Define sequential batch execution of multiple backtest candidates with
per-candidate failure isolation and an immutable batch summary.
## Requirements
### Requirement: Candidate validity

A batch MUST contain at least one candidate and unique candidate/run
identities.

#### Scenario: Duplicate candidate identity

- **WHEN** a batch request contains two candidates with the same run
  identity
- **THEN** the batch is rejected before any candidate executes.

### Requirement: Sequential execution order

Candidates MUST execute in request order.

#### Scenario: Execution order

- **WHEN** a batch of candidates runs
- **THEN** they execute in the exact order they appear in the request.

### Requirement: Failure isolation

One candidate failure MUST NOT prevent later candidates from running.

#### Scenario: A candidate fails mid-batch

- **WHEN** one candidate's backtest fails
- **THEN** subsequent candidates in the batch still execute.

### Requirement: Authoritative per-candidate path

Successful candidates MUST use the existing authoritative single-instance
backtest and atomic run-artifact path. After I8
(`compact-strategy-evaluation-boundary-v1`, `research-batch-lifecycle-v1`),
that path is `MaterializeBacktestProjectionOutcome` →
`PersistSingleInstanceRun` — the same canonical, `HistoricalExecutionProjection`
(`.v2`)-based components single-instance production uses, not the
legacy `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest` pair
(deleted once this migration lands). A candidate's row in the batch
result is a compact research summary of that already-materialized and
already-persisted canonical run — it is NOT a separate run format, NOT
a copy of the Strategy Engine's evaluation output, NOT a store of dense
per-bar data, and NOT a diagnostics artifact. A successful candidate row
MUST NOT appear in the batch result until
`MaterializeBacktestProjectionOutcome` and the atomic persist step have
both succeeded for that candidate.

#### Scenario: No independent execution logic

- **WHEN** a candidate succeeds
- **THEN** its result was produced through the same
  `MaterializeBacktestProjectionOutcome` → `PersistSingleInstanceRun`
  path used outside batches, with no batch-specific execution or
  accounting logic.

#### Scenario: Successful row summarizes a persisted run, not an in-flight evaluation

- **WHEN** a candidate's Strategy Engine evaluation succeeds but its
  materialize or persist step subsequently fails
- **THEN** the candidate's row in the batch result reports `status:
  failed`, and none of the successful-candidate summary fields
  (`return_pct`, `win_rate`, `profit_factor`, `max_drawdown`, `long`,
  `short`) are populated for it.

#### Scenario: Summary fields never carry dense evaluation data

- **WHEN** a batch candidate's row is inspected
- **THEN** it contains only scalar accounting totals and derived scalar
  metrics — never Strategy Engine per-bar/dense projection data, or any
  other dense per-bar payload.

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
  `max_drawdown`, `long` (`BatchSideSummary`), `short`
  (`BatchSideSummary`).

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

#### Scenario: long/short summaries use the same formulas per side

- **WHEN** a successful candidate's `long` and `short` summaries are
  computed
- **THEN** each equals `return_pct`/`win_rate`/`profit_factor`/`net_pnl`
  computed with the same formulas above, restricted to that candidate's
  trades with matching `side`, using the candidate's own
  `initial_equity` as the `return_pct` denominator for both sides.

#### Scenario: Sharpe and trade-quality counters are not included

- **WHEN** a successful candidate's row is inspected
- **THEN** it does not include a Sharpe ratio, trade-quality counters
  (e.g. high-MFE-capture or stop-loss-after-low-MFE counts), or any
  exit-reason/profile breakdown — none of these aggregates exist in the
  current persisted run artifact (which retains raw per-trade facts
  only), and producing them is outside this batch-summary change.

### Requirement: Atomic, immutable batch artifacts

Batch artifacts MUST publish atomically and MUST be immutable for an
experiment ID.

#### Scenario: Re-running an experiment ID

- **WHEN** a batch is submitted with an `experiment_id` that already has a
  published summary
- **THEN** the existing batch summary is not overwritten.

### Requirement: BatchSideSummary shape

A `BatchSideSummary` (used for a successful candidate's `long` and
`short` fields) SHALL contain exactly: `trades` (count), `net_pnl`,
`return_pct`, `win_rate` (nullable), `profit_factor` (nullable) — no
dense or per-trade data.

#### Scenario: Side with zero trades

- **WHEN** a candidate has zero trades on one side
- **THEN** that side's summary reports `trades: 0`, `net_pnl: 0`,
  `return_pct: 0`, `win_rate: null`, `profit_factor: null`.

### Requirement: Canonical position-sizing path

Every batch candidate SHALL inherit the same current-equity historical sizing lifecycle used by a direct single-instance backtest through the shared authoritative materializer. Batch orchestration SHALL NOT calculate, override, default, or post-process quantity or equity independently.

#### Scenario: Same candidate in single and batch

- **WHEN** the same candidate, market frame, execution assumptions, accounting policy, and Strategy Engine projection are materialized directly and inside a batch
- **THEN** their entry quantities, notionals, fees, PnL, equity chain, and final equity are identical.

#### Scenario: One candidate reaches impossible financial state

- **WHEN** a candidate's canonical sizing/accounting lifecycle fails closed
- **THEN** that candidate is reported failed under existing failure isolation
- **AND** later candidates may run without inheriting its equity or state.

