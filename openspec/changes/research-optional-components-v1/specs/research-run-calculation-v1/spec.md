## ADDED Requirements

### Requirement: Rows with an option off are calculable

A row whose option cell is empty SHALL be planned and calculated like any
other row, and the result row SHALL keep its empty option cell. The plan SHALL list
`option_inconsistent` among its skip reasons.

#### Scenario: Both kinds on one Surface

- **WHEN** a plan is requested for a row with a break-even trigger and a row
  without one, both without a run
- **THEN** both are calculable and the rows keep their option cells after publish.

### Requirement: Calculate may create a row from coordinates

When the coordinates of a requested row match no row of the table and every
column bound by the `materialize` block (main bindings and bindings of the
options that are on) is a dimension column whose value the coordinates carry,
the plan SHALL list the row as calculable with `new_row: true` instead of
`row_not_found`. Materialize SHALL read those values from the coordinates (for a
grid dimension, the value in the requested grid). A row whose bound columns
cannot all be read from the coordinates SHALL be skipped as `row_not_creatable`
with the missing columns. A calculated new row SHALL be appended to the table
with the dimension columns from the coordinates, the metrics, `run_id` and
provenance `engine` from the Engine run and every other column empty; there is no
stored row to compare, so the parity gate is not applied to it. `plan_token`
SHALL cover the coordinates of new rows. A row that already exists keeps its
rules (`has_run`, `ambiguous_row`).

#### Scenario: Break-even on a Surface without break-even runs

- **WHEN** the plan is requested for a cell with the break-even option on whose
  coordinates have no row
- **THEN** the row is calculable with `new_row: true`, and after Calculate the
  table holds one new row with the run and the metrics.

#### Scenario: Bound column not in the coordinates

- **WHEN** a bound column is derived and not a dimension column
- **THEN** the row is skipped as `row_not_creatable`.

### Requirement: Optional dimension declares its values

A result-schema dimension with `optional: true` MAY declare `values`, the numbers
the option can take; the workbench SHALL offer them when no row carries a value, so a
cell that has no run can still be addressed.

#### Scenario: No row has a value yet

- **WHEN** the table has no row with a break-even trigger and the dimension
  declares `values`
- **THEN** the workbench offers those values and the plan accepts them as
  coordinates.

#### Scenario: Value outside the declared values

- **WHEN** an optional dimension declares `values` and a requested row carries a
  value that is not among them
- **THEN** the row is skipped as `coord_not_allowed`.
