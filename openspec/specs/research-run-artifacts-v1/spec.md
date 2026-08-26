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

The bundle SHALL retain the exact request, Strategy Engine evaluation,
execution events, realised trades, metrics, and full result.

#### Scenario: Bundle contents

- **WHEN** a run bundle is inspected
- **THEN** it contains the original request, the Strategy Engine
  evaluation, execution events, realised trades, metrics, and the full
  result, each as its own file.

### Requirement: Open position representation

An open position SHALL remain represented in `result.json`; persistence
SHALL NOT force an exit.

#### Scenario: Persisting a run with an open position

- **WHEN** the persisted backtest ended with an open position
- **THEN** `result.json` reports it open, with no synthetic exit fill
  added by persistence.
