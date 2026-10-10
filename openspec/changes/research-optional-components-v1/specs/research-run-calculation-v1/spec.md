## ADDED Requirements

### Requirement: Rows with an option off are calculable

A row whose option switch is `off` SHALL be planned and calculated like any
other row, and the result row SHALL keep its switch value. The plan SHALL list
`option_inconsistent` among its skip reasons.

#### Scenario: Both kinds on one Surface

- **WHEN** a plan is requested for a row with break-even `on` and a row with it
  `off`, both without a run
- **THEN** both are calculable and the rows keep their switch values after publish.
