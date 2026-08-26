# Research Component Catalog v1 Specification

## Purpose

Define the preserved Workbench component-catalog BFF route sourced from
Strategy Engine's Composer Catalog API.

## Requirements

### Requirement: Strategy Engine-sourced catalog

Research Service SHALL preserve the existing Workbench component-catalog
contract while sourcing its contents from Strategy Engine. It SHALL NOT
maintain an independent production copy of strategy component metadata.

#### Scenario: Catalog request

- **WHEN** the Workbench frontend calls the component-catalog route for a
  supported family
- **THEN** the response is sourced live from Strategy Engine's Composer
  Catalog API, not a locally stored copy.

### Requirement: Unsupported family rejection

Unsupported families SHALL return HTTP 400 without an upstream request.

#### Scenario: Unknown family requested

- **WHEN** a request names a family Research Service does not support
- **THEN** it returns HTTP 400 and no call is made to Strategy Engine.
