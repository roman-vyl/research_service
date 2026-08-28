## MODIFIED Requirements

### Requirement: Bundle completeness

The bundle SHALL retain the exact request, a compact Strategy Engine
execution evaluation (sparse decision events plus provenance, per
`strategy_engine`'s `compact-strategy-evaluation-boundary-v1`), execution
events, realised trades, metrics, and the canonical result. The
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
- **THEN** it contains the compact sparse decision-event contract only —
  no full copy of Strategy Engine's original response body.

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
