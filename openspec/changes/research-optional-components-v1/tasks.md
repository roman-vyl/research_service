## 1. Backend (research_service)

- [ ] 1.1 Models: `options` in the materialize block, `optional` on schema dimension; manifest validation D6.
- [ ] 1.2 Allow one column bound to several paths (drop column uniqueness, keep path uniqueness).
- [ ] 1.3 `_materialize`: insert the item for `on`, nothing for `off`, `binding_value_invalid` for an unparsable cell, `option_inconsistent` for mismatched option cells.
- [ ] 1.4 Row addressing: empty cell of an `optional` dimension is off, absent coordinate accepted.
- [ ] 1.5 Tests: off row has the same spec and `config_hash` as a template without the item; on row carries the item with the bound trigger; shared trigger column; unparsable cell; half-filled row; two options at once; Surface without options unchanged.
- [ ] 1.6 Real check on a copy of the fee4 trailing geometry manifest with a break-even option: plan and a 40-row Calculate with parity.

## 2. Out of Scope (recorded)

Frontend switch, Engine changes, group-A filter components, variants with more than two states, item ordering.

## 3. Verification

- [ ] 3.1 Owner manual check: a Surface with a break-even option shows it as a checkbox and Calculate fills both kinds of rows.
