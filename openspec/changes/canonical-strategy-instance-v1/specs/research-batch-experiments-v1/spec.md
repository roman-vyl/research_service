## MODIFIED Requirements

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

## ADDED Requirements

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
