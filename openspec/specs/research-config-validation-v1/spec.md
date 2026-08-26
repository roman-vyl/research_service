# Research Config Validation v1 Specification

## Purpose

Define the preserved Workbench config-validation route, which delegates
strategy-instance semantics to Strategy Engine while validating only the
research/execution envelope locally.

## Requirements

### Requirement: Preserved Workbench DTO

`POST /api/research/config/validate` SHALL preserve the Workbench response
DTO.

#### Scenario: Validation response shape

- **WHEN** a client calls `POST /api/research/config/validate`
- **THEN** the response uses the existing Workbench validation-result DTO.

### Requirement: Local envelope validation only

Research Service SHALL validate only research/execution envelope semantics
locally.

#### Scenario: Envelope-level error

- **WHEN** the research/execution envelope of a draft is malformed
- **THEN** Research Service reports that error itself, without calling
  Strategy Engine.

### Requirement: Delegated strategy semantics

Strategy instance semantics SHALL be delegated to Strategy Engine.

#### Scenario: Strategy instance validation

- **WHEN** the envelope is well-formed and a strategy instance needs
  semantic validation
- **THEN** Research Service delegates that check to Strategy Engine rather
  than validating strategy semantics itself.

### Requirement: Stable upstream error paths

Upstream validation errors SHALL retain stable paths and messages.

#### Scenario: Strategy Engine reports an invalid instance

- **WHEN** Strategy Engine returns a validation error for a strategy
  instance
- **THEN** the error's field path and message are passed through unchanged
  to the Workbench response.
