## ADDED Requirements

### Requirement: Optional components

A `materialize` block MAY carry `options`, each with a unique `id`, a `column`
holding `off` or `on`, and an `insert` with `path` (a JSON Pointer to a list in
the template), `item` (a complete component) and `bindings` whose pointers are
relative to the item. Materialize SHALL append a deep copy of `item` with its
bindings applied to the list when the row's switch is `on`, and SHALL add nothing
when it is `off`. A switch other than `off` or `on` SHALL skip the row as
`binding_value_invalid`. Research SHALL NOT interpret the item. A block whose
option path is not a list in the template, whose item binding path is absent from
the item, or whose switch column is absent from the table SHALL be invalid.

#### Scenario: Option off

- **WHEN** the switch of a row is `off`
- **THEN** the materialized spec equals the spec of the template alone and has its
  `config_hash`.

#### Scenario: Option on

- **WHEN** the switch is `on` and the trigger cell is 6
- **THEN** the spec contains the item once, with its trigger set to 6.

#### Scenario: Two options

- **WHEN** a block declares two options
- **THEN** each row materializes by the switch of each option independently.

### Requirement: Option-only cells

A result-schema dimension MAY declare `option`, the id of an option. Its cell
SHALL be empty when the option is `off` and filled when `on`. Row addressing
SHALL treat an empty cell of such a dimension as `off` and SHALL NOT drop the row.
A row where the switch is `off` with a filled option-only cell, or `on` with an
empty one, SHALL be skipped as `option_inconsistent`.

#### Scenario: Half-filled row

- **WHEN** the switch is `on` and its own parameter cell is empty
- **THEN** the row is skipped as `option_inconsistent` and is not treated as `off`.

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
