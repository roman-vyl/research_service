## MODIFIED Requirements

### Requirement: Strategy Engine-sourced catalog

Research Service SHALL preserve the existing Workbench component-catalog
contract while sourcing its contents from Strategy Engine, selected by
`strategy_id`. It SHALL NOT maintain an independent production copy of
strategy component metadata.

#### Scenario: Catalog request

- **WHEN** the Workbench frontend calls the component-catalog route for a
  supported `strategy_id`
- **THEN** the response is sourced live from Strategy Engine's Composer
  Catalog API, not a locally stored copy.

## REMOVED Requirements

### Requirement: Unsupported family rejection

**Reason**: `family` is retired in favor of `strategy_id`
(`canonical-strategy-instance-v1`); the same fail-closed behavior is
restated under the new selector name in "Unsupported strategy_id
rejection" below.

**Migration**: Callers that supplied `family` SHALL supply `strategy_id`
instead. No alias is provided.

## ADDED Requirements

### Requirement: Unsupported strategy_id rejection

Unsupported `strategy_id` values SHALL return HTTP 400 without an
upstream request.

#### Scenario: Unknown strategy_id requested

- **WHEN** a request names a `strategy_id` Research Service does not
  support
- **THEN** it returns HTTP 400 and no call is made to Strategy Engine.
