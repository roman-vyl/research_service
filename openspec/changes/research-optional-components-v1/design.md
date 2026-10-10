## Decisions

### D1. Option = switch + inserted item

```json
"options": [{
  "id": "break_even",
  "label": "Break-even",
  "column": "be_trigger_r",
  "insert": {
    "path": "/raw_spec/trade_management/exit_management/stop_management",
    "item": {"component_id": "initial_r_lock_stop", "instance_id": "be",
             "params": {"trigger_r": 0, "lock_r": 0}},
    "bindings": [{"column": "be_trigger_r", "path": "/params/trigger_r", "type": "number"}]
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

### D3. The switch is the optional dimension

No separate `off`/`on` column. The option's `column` is a dimension declared
`optional: true` in `result_schema`, the convention the workbench already uses
(checkbox, then slider; rows without a value are the "off" rows). Empty cell =
off, number = on. For break-even on the trailing geometry surface the column is
`be_trigger_r`; when its value must equal the trail trigger, the data simply
holds the same number in both columns (the `trigger_r` binding stays on the
trail component). Further parameter columns of an option are filled exactly when
the value column is; a half-filled row is `option_inconsistent`, not a silent
`off`.

### D4. Shared columns

The uniqueness rule "binding columns must be unique" is dropped; "binding paths
must be unique" stays (per target document). One column may then feed several
paths, for example when a Surface wants the break-even trigger to follow the
trail trigger column instead of holding its own. Item bindings are checked
against the item, not the template.

### D5. Dimensions that belong to an option

`Dimension` gains `optional: bool` (today ignored). `_Keys.row_key` returns a
key with `off` (a fixed token) for an empty cell of an optional dimension
instead of `None` (which drops the row); `request_key` accepts an absent or empty
coordinate for it. Other dimensions are unchanged.

### D6. Validation of the block

Invalid manifest (the block is rejected as today): option id not unique;
`insert.path` not a list in the template; item binding path absent from the item;
option column absent from the table header or not an `optional` dimension.

### D7. Cache and plan token

The `materialize` block hash already enters the plan token; options are part of
the block, so a change of options makes a stale plan.

## Risks

- Existing Surfaces have no `options`; the block without it behaves as today.
- Rows of both kinds already live on one table with an empty cell for off, which
  is the stored convention; no data migration.
- A boolean option without a number (no value to put in a column) has no
  representation in the workbench today; out of scope.
