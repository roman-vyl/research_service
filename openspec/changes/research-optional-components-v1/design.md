## Decisions

### D1. Option = switch + inserted item

```json
"options": [{
  "id": "break_even",
  "label": "Break-even",
  "column": "be",
  "insert": {
    "path": "/raw_spec/trade_management/exit_management/stop_management",
    "item": {"component_id": "initial_r_lock_stop", "instance_id": "be",
             "params": {"trigger_r": 0, "lock_r": 0}},
    "bindings": [{"column": "trigger_r", "path": "/params/trigger_r", "type": "number"}]
  }
}]
```

`path` must point to a list in the template and `item` is a complete component
as the Engine expects it. Constants live in `item` (`lock_r: 0`); bindings only
copy cells, as before. Research never reads `component_id`.

Insertion is an append. If ordering ever matters for a component, a later change
adds an explicit position; no ordering is promised now.

### D2. `off` is the absence of the item

`off` adds nothing, so the spec is identical to the template's. Same
`config_hash` as a spec written without the component; no "disabled" flag in
Engine components is needed.

### D3. Switch column

`column` holds `off` or `on`. Anything else, including empty, makes the row
`binding_value_invalid`. An explicit switch is preferred over "all parameter
cells empty = off": a half-filled row is an error, not a silent `off`.

### D4. Shared columns

The uniqueness rule "binding columns must be unique" is dropped; "binding paths
must be unique" stays (per target document). Trailing geometry feeds the trail
trigger and the break-even trigger from one `trigger_r` column: one column, two
paths. Item bindings are checked against the item, not the template.

### D5. Dimensions that belong to an option

A dimension with `option: <id>` has an empty cell when that option is `off`.
`_Keys.row_key` and `request_key` treat such an empty cell as the value `off`
instead of dropping the row; the option's own switch is also a dimension
(single column, unit `switch`, values `off`/`on`) so a row is addressed by it.
Dimensions fed by columns shared with the template (the trigger of the example)
are ordinary dimensions and are never empty.

### D6. Validation of the block

Invalid manifest (the block is rejected as today): option id not unique;
`insert.path` not a list in the template; item binding path absent from the item;
switch column absent from the table header.

### D7. Cache and plan token

The `materialize` block hash already enters the plan token; options are part of
the block, so a change of options makes a stale plan.

## Risks

- Existing Surfaces have no `options`; the block without it behaves as today.
- A Surface that already stores rows of both kinds (BE on and off) without a
  switch column cannot be calculated until the column exists; adding it is a data
  preparation step, not runtime.
