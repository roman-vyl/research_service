## 1. Backend (research_service)

- [x] 1.1 Models: `options` in the materialize block, `optional` on schema dimension; manifest validation D6.
- [x] 1.2 Allow one column bound to several paths (drop column uniqueness, keep path uniqueness).
- [x] 1.3 `_materialize`: insert the item for `on`, nothing for `off`, `binding_value_invalid` for an unparsable cell, `option_inconsistent` for mismatched option cells.
- [x] 1.4 Row addressing: empty cell of an `optional` dimension is off, absent coordinate accepted.
- [x] 1.5 Tests: off row has the same spec and `config_hash` as a template without the item; on row carries the item with the bound trigger; shared trigger column; unparsable cell; half-filled row; two options at once; Surface without options unchanged.
- [ ] 1.6 Real check on a copy of the fee4 trailing geometry manifest with a break-even option: plan and a 40-row Calculate with parity. (Not done as specified: the feature was checked by the owner by hand on the frontend instead.)

- [x] 1.7 Create rows from coordinates: plan `new_row` / `row_not_creatable`, materialize from coordinates, append on publish without parity, token over new coordinates.
- [x] 1.8 `values` on an optional dimension (schema model only; the workbench change is separate).

- [x] 1.9 First user: fee4 trailing geometry manifest gets the `be_trigger` dimension (`optional`, unit R, `values` 2, 3, 4, 6, 8, 10) together with `materialize.options` (break-even, `lock_r` 0), after the service is deployed; the empty `be_trigger_r` column is already in the table.

## 2. Out of Scope (recorded)

Frontend switch, Engine changes, group-A filter components, variants with more than two states, item ordering.

## 3. Verification

- [x] 3.1 Owner manual check: a Surface with a break-even option shows it as a checkbox and Calculate fills both kinds of rows.
