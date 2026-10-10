## ADDED Requirements

### Requirement: Optional components

A `materialize` block MAY carry `options`, each with a unique `id`, a `column`
(a dimension declared `optional: true`; empty means off, filled means on), and an `insert` with `path` (a JSON Pointer to a list in
the template), `item` (a complete component) and `bindings` whose pointers are
relative to the item. Materialize SHALL append a deep copy of `item` with its
bindings applied to the list when the row's option cell is filled, and SHALL add
nothing when it is empty. A filled cell that cannot be parsed SHALL skip the row
as `binding_value_invalid`. Research SHALL NOT interpret the item. A block whose
option path is not a list in the template, whose item binding path is absent from
the item, or whose option column is absent from the table or not an `optional`
dimension SHALL be invalid.

#### Scenario: Option off

- **WHEN** the option cell of a row is empty
- **THEN** the materialized spec equals the spec of the template alone and has its
  `config_hash`.

#### Scenario: Option on

- **WHEN** the option cell is 6
- **THEN** the spec contains the item once, with its trigger set to 6.

#### Scenario: Two options

- **WHEN** a block declares two options
- **THEN** each row materializes by the cell of each option independently.

### Requirement: Option-only cells

A result-schema dimension MAY declare `optional: true`. Row addressing SHALL
treat an empty cell of such a dimension as off and SHALL NOT drop the row. An
option MAY name further parameter columns; they SHALL be filled exactly when the
option's own column is filled, otherwise the row SHALL be skipped as
`option_inconsistent`.

#### Scenario: Half-filled row

- **WHEN** the option cell is filled and its second parameter cell is empty
- **THEN** the row is skipped as `option_inconsistent` and is not treated as off.

## MODIFIED Requirements

### Requirement: Bindings copy values only

A binding SHALL declare `column`, `path` (an RFC 6901 JSON Pointer that exists in
the template) and `type` (`number`, `integer` or `string`). A column MAY be bound
to several paths; a path SHALL be bound once. Materialize SHALL deep-copy the
template and, for each binding, set the value at `path` to the row's cell parsed
as `type`. Bindings SHALL NOT carry formulas or unit conversions. A binding whose
path is absent from the template or whose column is absent from the table SHALL
make the block invalid.

#### Scenario: Derived take profit

- **WHEN** a Surface has a ratio axis and the template's take-profit multiplier
  is bound
- **THEN** it is bound to a table column that already holds SL × ratio, not to the
  ratio column.

#### Scenario: Unparsable cell

- **WHEN** a bound cell is empty or cannot be parsed as its type
- **THEN** the row is skipped as `binding_value_invalid`.

#### Scenario: One column, two paths

- **WHEN** the trail trigger and the break-even trigger take their value from one
  column
- **THEN** both paths receive the same cell value.

### Requirement: Rows are addressed by coordinates

A row SHALL be addressed by `coords`, keyed by the ids the results route filters
on: a value for every dimension id of `result_schema` (for a grid dimension, its
value in that grid together with `grid`; `arm` when arms are declared); an
`optional` dimension MAY be omitted or empty, which addresses the row without it.
Numeric columns SHALL be compared as numbers, others as text. At most one row
SHALL match; several matches SHALL be `ambiguous_row`. Coordinates that match no
row are handled by Calculate (a new row, or `row_not_creatable`).

#### Scenario: Duplicate coordinates

- **WHEN** two rows of the table have the same coordinates
- **THEN** a request for those coordinates skips the row as `ambiguous_row` and
  neither row is calculated.

#### Scenario: Optional dimension omitted

- **WHEN** a request names no value for an optional dimension
- **THEN** it addresses the row whose cell for that dimension is empty.
