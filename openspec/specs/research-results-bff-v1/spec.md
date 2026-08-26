# Research Results BFF v1 Specification

## Purpose

Define the read-side BFF over published run artifact bundles: list, latest,
detail, summary, trades, and metrics.

## Requirements

### Requirement: Read-only projection of published bundles

Research Service SHALL expose published run artifacts through
`/api/research/runs*` without reading or executing legacy BBB result code.

#### Scenario: Serving a run detail

- **WHEN** `/api/research/runs/{run_id}` is called
- **THEN** the response is projected directly from the persisted run
  bundle, with no legacy result code involved.

### Requirement: List ordering

Lists SHALL sort by manifest creation time descending.

#### Scenario: Listing runs

- **WHEN** the runs list route is called
- **THEN** the most recently created run bundle appears first.

### Requirement: Missing run handling

Missing runs SHALL return 404.

#### Scenario: Unknown run_id

- **WHEN** a route names a `run_id` with no persisted bundle
- **THEN** the response is HTTP 404.

### Requirement: Invalid bundle handling

Invalid versioned artifacts SHALL return a stable server error.

#### Scenario: Corrupted or mismatched-version bundle

- **WHEN** a persisted bundle fails manifest verification or carries an
  unsupported contract version
- **THEN** the route returns a stable structured server error rather than a
  partially projected response.

### Requirement: Direct projections

Trades and metrics SHALL be direct projections of the persisted
authoritative result.

#### Scenario: Trades/metrics route

- **WHEN** the trades or metrics route is called for a run
- **THEN** the response is read directly from that run's persisted
  `result.json`, with no recalculation.
