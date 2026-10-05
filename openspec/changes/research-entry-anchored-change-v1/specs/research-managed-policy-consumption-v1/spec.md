## MODIFIED Requirements

### Requirement: Projection contract decoding

Research Service MUST decode the Strategy Engine
`HistoricalManagedProjection` wire contract of baseline `07ff911`. A
`phase_transition` rule MUST carry exactly one of: `condition_id`;
(`distance_id`, `trade_metric`); a non-empty `paths` list. Each path
carries `path_id`, an optional `condition_id`, `thresholds`
(`distance_id`, `trade_metric`), an optional `entry_changes` list
(`series_id`, `op`, `value`), and an optional `at_least` (`k`,
`terms`, where each term has exactly one of `condition_id`,
(`distance_id`, `trade_metric`) or `entry_change`). Unknown fields, a
violated XOR, or a `condition_id`/`distance_id`/`series_id` reference
missing from `conditions` or `distances` MUST fail decoding.

#### Scenario: Composite rule decodes

- **WHEN** Strategy Engine sends a `phase_transition` rule with
  `condition_id`, `distance_id` and `trade_metric` null and a `paths`
  list
- **THEN** Research decodes it without error.

#### Scenario: Atomic rule unchanged

- **WHEN** Strategy Engine sends an atomic `phase_transition` rule
  without a `paths` key
- **THEN** Research decodes it exactly as before this change.

#### Scenario: Dangling reference rejected

- **WHEN** a path threshold references a `distance_id` absent from
  `distances`
- **THEN** decoding fails with an upstream contract error.

#### Scenario: Path without entry changes unchanged

- **WHEN** a path carries no `entry_changes` key and no term carries an
  `entry_change`
- **THEN** Research decodes and resolves it exactly as before this
  change.

### Requirement: Generic path resolution

Research Service MUST resolve a `paths` rule generically: a path is
true on a bar if and only if its `condition_id` (if any) is true for
the trade side, every threshold holds (`trade_metric >= distance`, with
a null distance false), every entry change holds (requirement
"Entry-anchored change terms"), and its `at_least` (if any) has at
least `k` true terms. The rule MUST fire on the first true path in
order, and the path's `path_id` MUST be attributed. Research MUST NOT
branch on a component name, component ID, or strategy parameter.

#### Scenario: First path wins

- **WHEN** paths `fast` and `htf` are both true on the same bar
- **THEN** the transition is attributed to `fast`.

#### Scenario: Mixed market and trade

- **WHEN** a path's market condition is true but its MFE threshold is
  not yet met
- **THEN** the path is false on that bar.

#### Scenario: Trade-only N-of-M

- **WHEN** an `at_least` with `k = 2` has three trade terms and exactly
  two hold
- **THEN** the path is true.

## ADDED Requirements

### Requirement: Entry-anchored change terms

An entry change `{series_id, op, value}` SHALL be evaluated for a
position whose entry fill is on bar `e` as follows: on bar `i`, it holds
iff `distances[series_id][i]` and `distances[series_id][e]` are both
non-null and `distances[series_id][i] − distances[series_id][e] <op>
value`.

- `op` SHALL be one of `>=`, `>`, `<=`, `<`; any other value, or a
  non-finite `value`, SHALL fail decoding.
- The anchor `distances[series_id][e]` SHALL be the same on every bar of
  the trade.
- The eager timeline builder and the incremental advance SHALL evaluate
  it identically.
- An entry-change term in `at_least` SHALL count as one term.
- Dispatch SHALL remain on the wire shape; Research SHALL NOT read a
  component id or a feature name.

#### Scenario: Rise from the entry value

- **GIVEN** a position entered on bar 10 and a series with value 21 on
  bar 10 and 26 on bar 13
- **WHEN** a path requires an entry change with `op` `>=` and `value` 5
- **THEN** the path SHALL be true on bar 13 and false on bars 10 to 12
  where the series is below 26.

#### Scenario: Entry bar

- **WHEN** `op` is `>=`, `value` is 0 and the series is non-null on the
  entry bar
- **THEN** the term SHALL hold on the entry bar.

#### Scenario: Null anchor

- **WHEN** the series is null on the entry bar
- **THEN** the term SHALL never hold for that position.

#### Scenario: Entry change inside N-of-M

- **WHEN** an `at_least` with `k = 2` has an entry-change term, an
  `mfe_pct` term and a market term, and only the entry change and the
  market term hold
- **THEN** the path SHALL be true.

#### Scenario: Incremental advance

- **WHEN** the incremental advance steps a position through bars of a
  projection with entry changes
- **THEN** its phases and attributed paths SHALL equal the eager
  timeline's bar for bar.
