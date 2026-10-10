## ADDED Requirements

### Requirement: Rows with an option off are calculable

A row whose option cell is empty SHALL be planned and calculated like any
other row, and the result row SHALL keep its empty option cell. The plan SHALL list
`option_inconsistent` among its skip reasons.

#### Scenario: Both kinds on one Surface

- **WHEN** a plan is requested for a row with a break-even trigger and a row
  without one, both without a run
- **THEN** both are calculable and the rows keep their option cells after publish.
