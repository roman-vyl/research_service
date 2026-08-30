## MODIFIED Requirements

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
