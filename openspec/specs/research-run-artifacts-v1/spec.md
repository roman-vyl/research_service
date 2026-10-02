# Research Run Artifacts v1 Specification

## Purpose

Define atomic, immutable persistence of a completed backtest as a versioned
run bundle with SHA-256 provenance.
## Requirements
### Requirement: Run directory layout

A completed backtest SHALL be persisted under `<artifacts_root>/<run_id>/`.

#### Scenario: Successful persistence

- **WHEN** a backtest completes and is persisted
- **THEN** its files exist under `<artifacts_root>/<run_id>/`.

### Requirement: Atomic publication

Publication SHALL be atomic at directory level.

#### Scenario: Publication interrupted

- **WHEN** persistence is interrupted before completion
- **THEN** no partially written run directory becomes visible at the final
  `run_id` path; a failed temporary bundle is cleaned up instead.

### Requirement: Immutable run ID

A run ID SHALL be immutable after publication.

#### Scenario: Re-publishing an existing run_id

- **WHEN** a backtest is submitted with a `run_id` that already exists
- **THEN** the existing bundle is not overwritten.

### Requirement: Manifest provenance

The manifest SHALL identify all non-manifest files by relative path,
SHA-256, and byte size.

#### Scenario: Manifest contents

- **WHEN** a run bundle's manifest is read
- **THEN** every other file in the bundle is listed with its relative path,
  SHA-256 hash, and byte size.

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

### Requirement: Open position representation

An open position SHALL remain represented in `result.json`; persistence
SHALL NOT force an exit.

#### Scenario: Persisting a run with an open position

- **WHEN** the persisted backtest ended with an open position
- **THEN** `result.json` reports it open, with no synthetic exit fill
  added by persistence.

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

### Requirement: Partial take content in run artifacts

When a run has partial takes:

- `strategy_evaluation.json` SHALL carry each opportunity's
  `partial_takes`;
- `execution_events.json` SHALL carry `position_reduced` events;
- `trades.json` SHALL carry each record's `exit_fills` and
  `average_exit_price`.

Previously persisted artifacts without these fields SHALL still be read.

#### Scenario: Read an artifact written before this change

- **WHEN** `trades.json` from a run before this change is read
- **THEN** every record SHALL load with an empty `exit_fills` and no
  `average_exit_price`.

### Requirement: Byte-identical artifacts without partial takes

For a strategy without partial takes, on market data where no bar opens
beyond an active stop, managed-stop or final take level, every persisted
artifact SHALL be byte-identical to the artifact the same run produced
before this change:

- `strategy_evaluation.json`;
- `trades.json`;
- `execution_events.json`;
- `metrics.json`.

`result.json` SHALL differ only by its run identity.

Empty ladder fields SHALL be omitted rather than written as an empty list
or null.

A bar that opens beyond such a level MAY change the stop or final fill
from the open to the level, as the level-fill model requires. That
change SHALL NOT count as a regression.

#### Scenario: Regression gate without legs

- **WHEN** a recorded run without partial takes is re-executed and
  persisted after this change
- **THEN** each of those files SHALL have the same sha256 as before
- **AND** `result.json` SHALL equal the earlier one once `run_id` is
  removed.

#### Scenario: Gap-through bar without legs

- **WHEN** a run without partial takes has a long stop at 95 and a bar
  opens at 90
- **THEN** the trade SHALL close at 95, where it closed at 90 before
  this change
- **AND** the regression gate SHALL NOT treat that difference as a
  failure.

