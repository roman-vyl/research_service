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
backtest and atomic run-artifact path.

#### Scenario: No independent execution logic

- **WHEN** a candidate succeeds
- **THEN** its result was produced by the same single-instance backtest use
  case and persisted through the same atomic artifact path used outside
  batches.

### Requirement: Batch output shape

Batch output MUST retain candidate order and expose completed/failed
counts.

#### Scenario: Batch summary contents

- **WHEN** a batch completes
- **THEN** its summary lists candidates in request order and reports how
  many completed versus failed.

### Requirement: Atomic, immutable batch artifacts

Batch artifacts MUST publish atomically and MUST be immutable for an
experiment ID.

#### Scenario: Re-running an experiment ID

- **WHEN** a batch is submitted with an `experiment_id` that already has a
  published summary
- **THEN** the existing batch summary is not overwritten.
