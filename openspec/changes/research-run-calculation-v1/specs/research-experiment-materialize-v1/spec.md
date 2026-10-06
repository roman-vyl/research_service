## ADDED Requirements

### Requirement: Materialize block

An Experiment manifest MAY carry a `materialize` block with `contract_version`
`research_experiment_materialize.v1`, a `strategy_template`, `bindings`,
`result_bindings` and a `research_policy`. The `strategy_template` SHALL be a
complete deployable strategy instance (`enabled`, `strategy_id`, `ticker`,
`base_timeframe`, `raw_spec`) in which every value that is not bound is frozen by
the Experiment. The `research_policy` SHALL carry the window, execution policy,
accounting policy and managed policy flag in the existing batch request shapes.
An Experiment without the block SHALL be served unchanged by the read routes.

#### Scenario: Frozen trigger

- **WHEN** the template sets the trigger lookback to 12 and no binding targets it
- **THEN** every spec materialized for that Experiment has trigger lookback 12.

#### Scenario: Same axis, different component

- **WHEN** two Experiments both have a `width` column but their templates use
  different width setup components
- **THEN** each row materializes to its own Experiment's component.

### Requirement: Bindings copy values only

A binding SHALL declare `column`, `path` (an RFC 6901 JSON Pointer that exists in
the template) and `type` (`number`, `integer` or `string`). Materialize SHALL
deep-copy the template and, for each binding, set the value at `path` to the row's
cell parsed as `type`. Bindings SHALL NOT carry formulas or unit conversions. A
binding whose path is absent from the template or whose column is absent from the
table SHALL make the block invalid.

#### Scenario: Derived take profit

- **WHEN** a Surface has a ratio axis and the template's take-profit multiplier
  is bound
- **THEN** it is bound to a table column that already holds SL × ratio, not to the
  ratio column.

#### Scenario: Unparsable cell

- **WHEN** a bound cell is empty or cannot be parsed as its type
- **THEN** the row is skipped as `binding_value_invalid`.

### Requirement: Engine validates every materialized spec

Research Service SHALL validate each materialized spec with Strategy Engine
`POST /strategies/{strategy_id}/validate` and SHALL keep the returned
`config_hash`. Research Service SHALL NOT interpret components or parameters of
the spec. An Engine validation error SHALL skip the row as `invalid_spec` with
Engine's message.

#### Scenario: Invalid parameter value

- **WHEN** a bound value is outside what the component accepts
- **THEN** the row is skipped as `invalid_spec` and no Engine run starts for it.

### Requirement: Rows are addressed by coordinates

A row SHALL be addressed by `coords`, keyed by the ids the results route filters
on: a value for every dimension id of `result_schema` (for a grid dimension, its
value in that grid together with `grid`; `arm` when arms are declared). Numeric columns SHALL be compared
as numbers, others as text. Exactly one row SHALL match; no match SHALL be
`row_not_found` and several matches SHALL be `ambiguous_row`.

#### Scenario: Duplicate coordinates

- **WHEN** two rows of the table have the same coordinates
- **THEN** a request for those coordinates skips the row as `ambiguous_row` and
  neither row is calculated.

### Requirement: Result bindings cover every metric

`result_bindings` SHALL map each metric column of `result_schema.metrics` to a
field of the Research run summary (dotted path for side summaries). An Experiment
in which a metric column has no result binding SHALL NOT be calculable
(`unbound_metric`).

#### Scenario: Metric without a source

- **WHEN** the table has a metric `years_positive` that the run summary does not
  provide
- **THEN** Calculate for that Experiment answers 409 `unbound_metric`.
