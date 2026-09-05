## ADDED Requirements

### Requirement: Complete worker-facing metric-role contract

For every stage kind, the interpretation worker-facing metric-role contract text SHALL explain
every `MetricRoles` field the mechanical validator enforces for that stage, including
`metric_roles.descriptive`. The contract text and the mechanical validator SHALL agree: a field the
mechanical validator constrains SHALL be explained to the worker, and the explanation SHALL NOT
permit a value the mechanical validator would reject.

#### Scenario: Descriptive role is explained for every stage kind

- **WHEN** the interpretation worker reads the rendered metric-role contract for any stage kind
- **THEN** the contract text states what `metric_roles.descriptive` must contain for that stage,
  never leaving the field unaddressed.

#### Scenario: Mechanical validator matches the stated contract

- **WHEN** a worker submits a `research_quality_assessment` whose `metric_roles.descriptive` value
  contradicts what the rendered contract text for the active stage states
- **THEN** the supervisor's mechanical validation rejects the submission with a clear cause, rather
  than accepting a value the contract text ruled out or rejecting a value the contract text never
  addressed.
