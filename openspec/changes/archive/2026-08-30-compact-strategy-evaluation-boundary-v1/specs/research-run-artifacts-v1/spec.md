## MODIFIED Requirements

### Requirement: Bundle completeness

The bundle SHALL retain the exact request, a compact Strategy Engine
execution evaluation (`HistoricalExecutionProjection` — executable entry
opportunities with locked exit profile and attributed initial
stop/take, per-profile-indexed signal-exit events with attribution, plus
provenance, per `strategy_engine`'s `compact-strategy-evaluation-
boundary-v1`), execution events, realised trades, metrics, and the
canonical result. The
canonical result file SHALL reference its execution evaluation by
identity rather than re-embedding it. Dense diagnostic data (feature
series, context data, component evidence, potential-entry traces) is
**not** part of the mandatory bundle — see the new "Diagnostics are a
separate optional artifact" requirement below.

#### Scenario: Bundle contents

- **WHEN** a run bundle is inspected
- **THEN** it contains the original request, the compact Strategy Engine
  execution evaluation, execution events, realised trades, metrics, and
  the canonical result, each as its own file
- **AND** the canonical result file contains no re-embedded copy of the
  execution evaluation.

#### Scenario: No raw Engine response body retained

- **WHEN** a run bundle's execution evaluation file is inspected
- **THEN** it contains the compact `HistoricalExecutionProjection` only —
  no full copy of Strategy Engine's original response body.

#### Scenario: Execution evaluation carries exit attribution

- **WHEN** a run bundle's execution evaluation file is inspected
- **THEN** every entry opportunity's initial stop/take and every signal-
  exit candidate carries `rule_id`/`component_id`/`exit_kind`
  attribution — not a bare ratio or boolean with no attribution.

## ADDED Requirements

### Requirement: Diagnostics are a separate, optional artifact

Dense diagnostic data (feature series, context data, component evidence,
potential-entry traces) SHALL NOT be persisted as part of every
backtest's mandatory bundle. It is generated and persisted only when
explicitly requested, as its own artifact scoped to the same `run_id`.

#### Scenario: A freshly completed run has no diagnostics yet

- **WHEN** a backtest completes and is persisted
- **THEN** its bundle contains no dense diagnostic artifact
- **AND** requesting that run's trades/metrics/summary succeeds without
  one.

#### Scenario: Diagnostics generated on request

- **WHEN** diagnostics are explicitly requested for an existing run
- **THEN** Research Service generates them (calling Strategy Engine's
  diagnostic-evaluation entrypoint for the same immutable strategy and
  `market_data_hash`/range) and persists the result as a separate
  artifact scoped to that `run_id`
- **AND** the run's existing canonical result and execution-evaluation
  files are not modified by this generation step.

## ADDED Requirements

### Requirement: Production persistence shape cutover (I7)

After I7's coordinated cutover, single-instance production runs SHALL
be persisted in the I6.D-proven shape: `strategy_evaluation.json` IS
the real `HistoricalExecutionProjection`; `result.json` references it
(and `trades.json`/`execution_events.json`) by sha256 identity rather
than re-embedding, while retaining a lightweight market-identity/
provenance subset (`ticker`, `timeframe`, `from_ms`, `to_ms`,
`bar_count`, `market_data_hash`, `instance_id`, `config_hash`) directly
on `result.json` so identity-only consumers (e.g. run summaries) do not
need to open the referenced file. Batch-persisted artifacts are
unaffected — this requirement governs only the single-instance
production path. Full cutover coordination, compatibility, and rollback
requirements are normative in `research-production-cutover-v1`.

#### Scenario: Single-instance result.json carries identity without re-embedding

- **WHEN** a single-instance run is persisted after I7
- **THEN** `result.json` contains the market-identity subset directly
  and a sha256-identified reference to `strategy_evaluation.json`
- **AND** it does not contain the full re-embedded projection content.
