## Why

`BatchCandidateResult` today (`research-batch-experiments-v1`) carries only
raw accounting totals (`realised_trade_count`, `gross_pnl`, `fees_paid`,
`net_pnl`, `final_equity`, ...) with no comparison-ready metrics
(`return_pct`, `win_rate`, `profit_factor`, `max_drawdown`, long/short
split). Comparing candidates in a batch currently requires opening each
persisted `SingleInstanceBacktestResult` individually and computing these
by hand.

A legacy monolithic research system already solved this shape once: its
batch rows carried exactly these derived metrics, computed from
already-closed trade PnL after fees, with a later revision adding a
long/short split. Its trade-quality/exit-reason breakdowns, by contrast,
were never recomputed in the batch row itself. That split is the right
precedent: cheap, unambiguous per-trade aggregates belong in the compact
batch row; anything needing extra config (quality thresholds) or
per-bar/per-component detail is out of scope for this change and may be
derived by future or on-demand diagnostics work, not by this
batch-summary contract.

This change extends the existing `research-batch-experiments-v1`
capability's `BatchCandidateResult` shape with that same class of
derived, unambiguous metrics — computed strictly from the trade list on
the in-memory materialized canonical result, immediately after
successful persistence, never from Engine's raw evaluation output and
never by rereading anything from disk.

## What Changes

- Add `BatchSideSummary` (`trades`, `net_pnl`, `return_pct`, `win_rate |
  null`, `profit_factor | null`) as a new typed shape used for the
  long/short split.
- Extend a successful `BatchCandidateResult` with: `return_pct`,
  `win_rate | null`, `profit_factor | null`, `max_drawdown`,
  `long: BatchSideSummary`, `short: BatchSideSummary`.
- Fix exact, unambiguous formulas for each new metric (net-PnL-after-fees
  based, matching the legacy system's established semantics where it had
  one canonical definition; explicitly excluding Sharpe, which the legacy
  system computed two different, mutually inconsistent ways depending on
  execution path, so there is no single canonical formula to adopt).
- Make explicit (as a MODIFIED requirement, not new behavior) that a
  candidate row MUST NOT be appended to a batch result until the
  candidate's canonical run has been successfully materialized *and*
  persisted — a `BatchCandidateResult` is a summary of something that
  already exists on disk, never a preview of an in-flight evaluation.

## What Does Not Change

- No new run/result format. `SingleInstanceBacktestResult` and its
  persisted artifact shape are untouched.
- No dense per-bar data, Engine evidence, `features.series`, or
  `component_evidence` enters `BatchCandidateResult` — every new field is
  a scalar or small nested scalar object.
- No Sharpe ratio, no trade-quality counters (`high_mfe_*`,
  `stop_loss_after_*`), no exit-reason/profile breakdown, no path
  diagnostics — these are outside this batch-summary change; the
  persisted canonical run retains only raw per-trade facts today, and
  any such aggregate would have to be derived by future or on-demand
  diagnostics work, not by this contract.
- No change to Strategy Engine transport, `/range-batch` request/response
  shape, execution/accounting semantics, or frontend APIs.
- No change to `research-history-window-planning-v1` or
  `canonical-strategy-instance-v1`.

## Impact

- Affected capability: `research-batch-experiments-v1` (MODIFIED
  requirements only — no new capability).
- Affected code (implementation deferred to a follow-up task, not part of
  this proposal): `application/experiments/contracts.py`
  (`BatchCandidateResult`, new `BatchSideSummary`),
  `application/experiments/run_batch.py` (`_settle_candidate` — derive the
  new fields from the in-memory `materialized.result.accounting.trades`
  after successful persist, with no disk reread, before the candidate's
  working set is released).
