# Research Service Foundation v1 Specification

## Purpose

Define the cross-cutting service composition contract: the installable
package, its explicit external ports, its incomplete-capability contract,
its stable error envelope, and its operational endpoints. Business-capability
ownership is defined in `research-service-boundaries-v1`; per-route behavior
is defined in each capability's own spec.

## Requirements

### Requirement: Independent production package

The repository SHALL expose an installable `research_service` package under
`src/`. Production modules SHALL NOT import from `research` or `research_api`
(the historical monolith's own package names).

#### Scenario: Static import guard

- **WHEN** production source under `src/research_service/` is scanned for
  imports
- **THEN** it SHALL contain no reference to the `research` or `research_api`
  package names.

### Requirement: Explicit external ports

Strategy evaluation SHALL be accessed through `StrategyEnginePort`; canonical
candles SHALL be accessed through `MarketDataPort`; artifact persistence
SHALL be accessed through `ArtifactStore`.

#### Scenario: A use case needs an external dependency

- **WHEN** application code needs Strategy Engine output, candle data, or
  artifact storage
- **THEN** it depends on the corresponding port interface, not on a concrete
  HTTP client or filesystem path directly.

### Requirement: Honest incomplete capabilities

Preserved routes without a completed semantic port SHALL return HTTP 501
with `error=capability_not_ported`.

#### Scenario: An unported route is called

- **WHEN** a client calls a preserved Workbench route whose backing use case
  is not yet implemented
- **THEN** the response is HTTP 501 with `code=capability_not_ported` and no
  legacy code executes and no fake-success payload is returned.

### Requirement: Stable error envelope

Every non-2xx API response SHALL use the Research Service error envelope
(`code`, `message`, `status_code`, and optional `details`).

#### Scenario: An upstream service fails

- **WHEN** Strategy Engine or Market Data Service returns an error or is
  unavailable
- **THEN** the Research Service response maps it through the same envelope
  shape rather than passing the raw upstream payload through.

### Requirement: Operational endpoints

`GET /health` SHALL report process liveness. `GET /readiness` SHALL report
Strategy Engine and Market Data Service dependency health and artifact-store
location.

#### Scenario: Readiness check

- **WHEN** an operator or orchestrator calls `GET /readiness`
- **THEN** the response reports the health of both upstream dependencies and
  the configured artifact-store location, and OpenAPI is available through
  the FastAPI default route.
