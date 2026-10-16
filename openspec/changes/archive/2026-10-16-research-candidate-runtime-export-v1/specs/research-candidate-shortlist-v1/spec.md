## MODIFIED Requirements

### Requirement: Strategy spec is a historical snapshot

When the row has a `run_id`, a star SHALL copy the strategy spec from that run's
`request.json` into `strategy_spec_snapshot`; when it has none, the field SHALL be
null; when the file cannot be read, the star SHALL still succeed and record the
reason. The snapshot SHALL be served as a record of what was picked; it is not
kept in sync with the current row. The owner MAY export it to the Strategy
Runtime catalog (`research-candidate-runtime-export-v1`); whether it is fit for
Runtime is the owner's decision, not Research's.

#### Scenario: Replay point

- **WHEN** a replay row without `run_id` is starred
- **THEN** the record is stored with `strategy_spec_snapshot` null.
