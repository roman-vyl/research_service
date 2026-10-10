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

- `materialize.options`: a list of optional components. Each has an `id`, a
  switch `column` holding `off` or `on`, an `insert` (a JSON Pointer to a list in
  the template and the complete item to add, with `bindings` whose pointers are
  relative to the item).
- Materialize adds the item to the template when the row's switch is `on`;
  nothing is added when `off`. An `off` row yields exactly the spec the template
  alone yields, so it has the same `config_hash` as a spec without the component.
- A binding column may feed several paths (today each column is bound once).
- A result-schema dimension may be marked as belonging to an option
  (`option`: id). Its cell is empty when the option is `off` and required when
  `on`; row addressing treats an empty cell of such a dimension as a value `off`
  and does not drop the row.
- A row with the switch `off` and a filled option-only cell, or `on` and an empty
  one, is skipped as `option_inconsistent`.
- No change to Strategy Engine. No interpretation of components in Research: it
  only inserts the declared item.

## Out of scope

- Group-A filters stay replay-only; they have no Engine component yet.
- Choosing among more than two states (variant 1/2/3); this change is a binary
  switch per option. Several options may coexist, each with its own switch.
- Frontend: the switch is a dimension with `option` metadata read from the
  manifest; the frontend change is separate and small, specified in
  `research_frontend`.
- The Engine memory failure of large Calculate batches (separate thread).

## Impact

- `domain/experiment_materialize.py`, `domain/experiment_schema.py`.
- `adapters/experiments/run_calculation.py` (`_materialize`, `_Keys`).
- Specs: `research-experiment-materialize-v1`, `research-run-calculation-v1`.
- First user: manifest of `btcusdt_p.ema500.trailing_geometry_fee4_4d`
  (break-even option); the data/manifest edit is done separately on request.
