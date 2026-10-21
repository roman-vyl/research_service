## MODIFIED Requirements

### Requirement: Stable errors on unknown references

Unknown single-run strategy instances and context overlay references
SHALL return stable invalid-request errors. The wire identity for a
diagnostics request is the run's canonical `instance_id`
(`canonical-strategy-instance-v1`), addressed via the `instance_id` query
parameter — not the retired `variant` parameter name.

#### Scenario: Unknown context overlay

- **WHEN** a request names a context overlay that does not exist for the
  run
- **THEN** the response is a stable `invalid_request` error.

#### Scenario: instance_id does not match the run

- **WHEN** a diagnostics request's `instance_id` query parameter does not
  match the run's own `instance_id`
- **THEN** the response is a stable `invalid_request` error.

#### Scenario: Legacy variant query parameter is not accepted

- **WHEN** a diagnostics request supplies the retired `variant` query
  parameter instead of `instance_id`
- **THEN** the request is rejected as invalid before any diagnostics
  projection is built — `variant` is not an accepted alias for
  `instance_id`.
