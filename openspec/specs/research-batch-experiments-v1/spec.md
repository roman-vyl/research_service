# Research Batch Experiments v1 Specification

## Purpose

Define sequential batch execution of multiple backtest candidates with
per-candidate failure isolation and an immutable batch summary.
## Requirements
### Requirement: Candidate validity

A batch MUST contain at least one candidate and unique `candidate_id`
values. `run_id` SHALL NOT be part of a batch candidate request and SHALL
NOT be used for pre-execution uniqueness validation — it does not exist
until a candidate has run, since `run_id` is Research-generated per
`research-backtest-api-v1`.

#### Scenario: Duplicate candidate identity

- **WHEN** a batch request contains two candidates with the same
  `candidate_id`
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

### Requirement: One candidate is one canonical strategy instance

Each batch candidate SHALL wrap exactly one canonical deployable strategy
instance (`canonical-strategy-instance-v1`:
`{enabled, strategy_id, ticker, base_timeframe, raw_spec}`) plus its own
Research-owned evaluation concerns (execution policy, accounting policy,
`managed_policy_enabled`, metadata). A candidate SHALL NOT embed a
standalone `SingleInstanceBacktestRequest` — batch candidates and
standalone backtest requests are structurally distinct: a candidate
contributes only what legitimately varies between comparable
configurations, never its own range or its own market.

#### Scenario: Candidate strategy shape matches the canonical deployable instance

- **WHEN** a batch candidate's strategy input is inspected
- **THEN** it has the same shape as a canonical deployable strategy
  instance (`enabled`/`strategy_id`/`ticker`/`base_timeframe`/`raw_spec`),
  with no `family`, `variant`, `strategy_version`, caller-supplied
  `instance_id`, or `run_id`.

#### Scenario: Legacy embedded-backtest-request shape is rejected

- **WHEN** a batch candidate is submitted in the old shape (a nested
  standalone backtest request under a `backtest` field)
- **THEN** it is rejected — no compatibility alias or dual-schema
  acceptance is provided.

### Requirement: Experiment owns one range policy/window

A batch experiment SHALL carry exactly one `range_policy` and, for
`explicit_range`, exactly one shared `from_ms`/`to_ms` range at the
experiment level. No candidate SHALL carry its own range or range_policy.
An experiment compares configurations of one strategy over one
historical comparison window, not several independent windows.

#### Scenario: explicit_range requires one shared range

- **WHEN** an experiment's `range_policy` is `explicit_range`
- **THEN** the experiment SHALL include exactly one `range` with
  `from_ms`/`to_ms`, shared by every candidate.

#### Scenario: full_available carries no range

- **WHEN** an experiment's `range_policy` is `full_available`
- **THEN** the experiment SHALL NOT include a `range` — no dummy or
  placeholder `from_ms`/`to_ms` is accepted.

### Requirement: Every candidate shares strategy_id/ticker/base_timeframe

Every candidate in an experiment SHALL share the experiment's
`strategy_id`, and every candidate's `ticker` and `base_timeframe` SHALL
be identical across the whole experiment. Candidates MAY differ in
`raw_spec`, execution policy, accounting policy, `managed_policy_enabled`,
and metadata — never in comparison universe (strategy type, instrument,
or timeframe).

#### Scenario: Mismatched strategy_id is rejected

- **WHEN** a candidate's `strategy.strategy_id` differs from the
  experiment's `strategy_id`
- **THEN** the batch is rejected before any external call.

#### Scenario: Mismatched ticker or base_timeframe is rejected

- **WHEN** any two candidates in one experiment have different
  `strategy.ticker` or different `strategy.base_timeframe`
- **THEN** the batch is rejected before any external call.

### Requirement: Research issues exactly one Engine range-batch call per experiment

Research Service SHALL evaluate every candidate in one experiment through
exactly one Strategy Engine `/range-batch` call. Research SHALL NOT issue
a per-candidate Strategy Engine `/range` call for a batch experiment.

#### Scenario: N candidates, one Engine call

- **WHEN** an experiment with N candidates is executed
- **THEN** Strategy Engine's range-batch evaluation is called exactly
  once, and its single-range evaluation is called zero times.

### Requirement: Research supplies fail-closed market-data provenance to the shared Engine acquisition

Research Service SHALL supply the resolved window's
`expected_market_data_hash` on its `/range-batch` call, giving Strategy
Engine's shared L0 acquisition the same fail-closed provenance guarantee
standalone single-range evaluation already has — Engine verifies the
shared acquisition against it before evaluating any variant, rather than
Research trusting an unverified shared dataset.

#### Scenario: Batch request carries the resolved window's hash

- **WHEN** Research Service builds a Strategy Engine `/range-batch`
  request for an experiment
- **THEN** the request's `expected_market_data_hash` equals the
  experiment's resolved window's `market_data_hash`.

### Requirement: Research resolves the shared market window once

Research Service SHALL resolve the experiment's market window (via the
same window-resolution logic a standalone backtest uses) exactly once per
experiment, using the experiment's shared `ticker`/`base_timeframe`/range,
not once per candidate.

#### Scenario: N candidates, one window resolution

- **WHEN** an experiment with N candidates is executed
- **THEN** Market Data Service bounds/audit resolution happens exactly
  once for the whole experiment.

### Requirement: Research reads the shared MarketFrame once

Research Service SHALL read the historical `MarketFrame` for an
experiment's resolved window exactly once, and SHALL reuse that same
immutable frame for every candidate's execution/accounting — never
re-reading candles per candidate.

#### Scenario: N candidates, one historical read

- **WHEN** an experiment with N candidates is executed
- **THEN** Research Service's historical-range read happens exactly once,
  and every candidate's execution uses that same `MarketFrame`.

### Requirement: candidate_id is the Engine variant_id

A candidate's `candidate_id` SHALL be used directly as the Strategy
Engine `/range-batch` wire `variant_id` — no separate correlation
identity or translation table. `variant_id` is an ephemeral wire-only
correlation key; it SHALL NOT be persisted in run artifacts or exposed in
any public Research result alongside `candidate_id`/`instance_id`/
`run_id`/`experiment_id`.

#### Scenario: variant_id equals candidate_id on the wire

- **WHEN** Research Service builds a Strategy Engine `/range-batch`
  request for an experiment
- **THEN** each variant's `variant_id` equals its candidate's
  `candidate_id`.

### Requirement: Response correlation by variant_id, not array order

Research Service SHALL correlate each `/range-batch` response entry to
its requesting candidate by `variant_id`, never by response array
position. An unrequested `variant_id`, a duplicate `variant_id`, or a
missing outcome for a requested candidate SHALL fail the whole
experiment before any candidate materialization begins.

#### Scenario: Response order does not affect correlation

- **WHEN** Strategy Engine returns variant outcomes in a different order
  than they were requested
- **THEN** each outcome is still correctly attributed to its candidate.

#### Scenario: Malformed correlation fails the whole experiment

- **WHEN** a `/range-batch` response contains an unrequested
  `variant_id`, a duplicate `variant_id`, or omits an outcome for a
  requested candidate
- **THEN** the whole experiment fails before any candidate is
  materialized or persisted.

### Requirement: Three-level failure isolation

An experiment's failures SHALL be handled at exactly one of three levels.
(1) Whole-experiment failures — invalid experiment invariants, shared
window resolution failure, the Engine `/range-batch` call itself failing,
malformed response correlation, or the shared historical read failing —
SHALL fail the entire experiment before any candidate materialization
begins; no candidate SHALL receive a `run_id` or a persisted artifact.
(2) A per-variant Strategy Engine error (HTTP 200 with that variant's
`result` null and `error` populated) SHALL isolate only that candidate as
failed, with no materialization attempted for it, while sibling
candidates continue. (3) A per-candidate materialization or persistence
failure (contract acceptance, managed replay, execution, accounting, or
artifact persistence) SHALL isolate only that candidate as failed,
without disturbing already-persisted sibling candidates.

#### Scenario: Whole-experiment failure persists nothing

- **WHEN** shared window resolution or the Engine `/range-batch` call
  fails
- **THEN** no candidate is materialized, no `run_id` is generated, and no
  run artifact is persisted for any candidate.

#### Scenario: Per-variant Engine failure isolates one candidate

- **WHEN** one candidate's Engine variant outcome is an error
- **THEN** only that candidate is marked failed with no `run_id`, and
  sibling candidates are materialized and persisted normally.

#### Scenario: Per-candidate materialization failure does not roll back siblings

- **WHEN** one candidate's evaluation succeeds but materialization or
  persistence fails for it
- **THEN** only that candidate is marked failed with no `run_id`, and any
  sibling candidates already persisted remain persisted.

### Requirement: Successful candidates reuse the standalone materialization pipeline

Every successful candidate SHALL be materialized through the same
application seam a standalone backtest uses (execution, managed replay,
accounting, and per-candidate `run_id` generation only on success), and
persisted as an independent canonical single-instance run artifact
(`research-backtest-api-v1`) — batch execution SHALL NOT duplicate or
reimplement execution/accounting logic.

#### Scenario: Successful candidate produces a canonical run artifact

- **WHEN** a candidate completes successfully
- **THEN** it is persisted as the same canonical run-artifact shape a
  standalone `POST /api/research/backtests` run produces, with its own
  distinct `run_id`.

