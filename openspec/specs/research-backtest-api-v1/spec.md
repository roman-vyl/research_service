# Research Backtest API v1 Specification

## Purpose

Define the synchronous single-instance backtest HTTP endpoint.

## Requirements

### Requirement: Request contract

`POST /api/research/backtests` SHALL accept `SingleInstanceBacktestRequest`.

#### Scenario: Valid request accepted

- **WHEN** a well-formed `SingleInstanceBacktestRequest` is posted
- **THEN** the endpoint accepts it and begins orchestration.

### Requirement: Authoritative orchestration

The endpoint SHALL use the authoritative Strategy Engine and Market Data
Service ports through the existing single-instance orchestration use case.

#### Scenario: No independent logic

- **WHEN** the route handler is inspected
- **THEN** it delegates to the single-instance backtest use case rather
  than implementing its own Strategy Engine/MDS calls.

### Requirement: Atomic persistence before success

A successful run SHALL be atomically persisted before the endpoint returns
success.

#### Scenario: Response ordering

- **WHEN** the endpoint returns HTTP 201
- **THEN** the run bundle is already durably persisted at that point.

### Requirement: Success response

Success SHALL return HTTP 201 and contract version
`research_backtest_api.v1`.

#### Scenario: Successful response shape

- **WHEN** a backtest completes successfully
- **THEN** the response is HTTP 201 with `contract_version` equal to
  `research_backtest_api.v1`.

### Requirement: Response summary fields

The response SHALL identify the run, instance, realised trade count,
open-position count, final equity, net PnL, and artifact bundle.

#### Scenario: Response contents

- **WHEN** a successful response is inspected
- **THEN** it includes the run ID, instance ID, realised trade count,
  open-position count, final equity, net PnL, and the artifact bundle
  reference.

### Requirement: Duplicate run rejection

An existing immutable `run_id` SHALL return HTTP 409 `run_already_exists`.

#### Scenario: Re-submitting a run_id

- **WHEN** a request names a `run_id` that already has a persisted bundle
- **THEN** the endpoint returns HTTP 409 with `code=run_already_exists`.

### Requirement: No embedded domain logic

The route SHALL NOT implement strategy, execution, or accounting semantics.

#### Scenario: Route layering

- **WHEN** the route module is inspected
- **THEN** it contains no strategy, execution, or accounting calculation —
  only request/response mapping around the orchestration use case.
