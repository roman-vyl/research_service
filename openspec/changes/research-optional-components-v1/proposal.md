## Why

A Surface often studies a component that can be on or off, with its own
parameters when on: break-even (`initial_r_lock_stop` with a trigger R), a stop,
a take, an entry blocker. Today a manifest `materialize` block has one frozen
template and bindings that only copy cells, so such a Surface cannot be
calculated: a row with the component off has empty parameter cells, which skip as
`binding_value_invalid`, and a row whose dimension cell is empty is dropped from
row addressing. Each option also multiplies the number of runs, and the rows must
live on the same Surface as the rows without it.

The aim is a manifest language: the researcher declares an optional component
once; the Surface shows it as a switch; Calculate runs rows with and without it.
Break-even on the EMA500 trailing geometry surface is the first example, not the
purpose.

## What Changes

- The workbench already treats a result-schema dimension with `optional: true`
  as a switch: a row with an empty cell for it is an "off" row, a row with a
  number is "on". Research Service ignores the field today (`extra="ignore"`) and
  its row addressing drops rows with an empty dimension cell. This change makes
  Research Service honor the same convention.
- `materialize.options`: a list of optional components. Each has an `id`, the
  optional dimension's value `column` (empty = off, filled = on), an `insert` (a
  JSON Pointer to a list in the template and the complete item to add, with
  `bindings` whose pointers are relative to the item).
- Materialize adds the item to the template when the row's cell is filled;
  nothing is added when it is empty. An `off` row yields exactly the spec the template
  alone yields, so it has the same `config_hash` as a spec without the component.
- A binding column may feed several paths (today each column is bound once).
- Row addressing treats an empty cell of an `optional` dimension as "off" and
  does not drop the row.
- An option may have further parameter columns; they are filled exactly when the
  option's value column is filled. A row where they disagree is skipped as
  `option_inconsistent`.
- No change to Strategy Engine. No interpretation of components in Research: it
  only inserts the declared item.

## Out of scope

- Group-A filters stay replay-only; they have no Engine component yet.
- Choosing among more than two states (variant 1/2/3); this change is a binary
  switch per option. Several options may coexist, each with its own switch.
- Frontend: it already renders `optional: true` dimensions as a checkbox plus
  slider and filters "off" rows; no change is expected for a numeric option such
  as the break-even trigger.
- The Engine memory failure of large Calculate batches (separate thread).

## Impact

- `domain/experiment_materialize.py`, `domain/experiment_schema.py`.
- `adapters/experiments/run_calculation.py` (`_materialize`, `_Keys`).
- Specs: `research-experiment-materialize-v1`, `research-run-calculation-v1`.
- First user: manifest of `btcusdt_p.ema500.trailing_geometry_fee4_4d`
  (break-even option); the data/manifest edit is done separately on request.
