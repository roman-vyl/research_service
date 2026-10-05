## Why

Strategy Engine's managed projection (`HistoricalManagedProjection`) can now carry an entry-anchored change term
(Strategy Engine `entry-anchored-change-v1`, merged as strategy_engine #27). The term compares a per-bar series with its
own value on the trade's entry bar. Research Service decodes the projection with `extra="forbid"`, so today it rejects
any projection that contains such a term. Strategies whose phase conditions measure a feature's change since entry cannot
run until Research executes the term.

## What Changes

- Decode two new optional wire fields:
  - `ManagedTransitionPathDTO.entry_changes`: a list of `{series_id, op, value}`, default empty.
  - `ManagedTransitionTermDTO.entry_change`: `{series_id, op, value}` or absent. An `at_least` term carries exactly one
    of `condition_id`, (`distance_id`, `trade_metric`) or `entry_change`.
  - `op` is one of `>=`, `>`, `<=`, `<`; `value` is a finite number; `series_id` must name a series in `distances`.
- Execute the term generically. For a position whose entry fill is on bar `e`, on bar `i` the term holds iff
  `series[i]` and `series[e]` are both non-null and `series[i] − series[e] <op> value`. A path is true only if every
  entry change holds, in addition to the existing conditions. An entry-change term counts toward `at_least` like any
  other term.
- The same evaluation in the eager timeline builder and in the incremental advance.
- Dispatch stays on the wire shape: Research reads no component id, feature name or strategy parameter.
- Nothing changes for projections without the new fields: same decode, same path results, same cost.

## Impact

- `research-managed-policy-consumption-v1`: MODIFIED `Projection contract decoding`, `Generic path resolution`; ADDED
  `Entry-anchored change terms`.
- Code: `domain/contracts.py` (DTOs and reference validation), `execution/managed_policy.py` (`_phase_rule_met`,
  `_path_met`, both call sites pass the entry bar index).

## Verification

- Decode tests: path and term with the new fields; an unknown `op`; a non-finite `value`; a term with two variants; a
  `series_id` missing from `distances`; a projection without the fields decodes exactly as before.
- Execution tests: `require` and `at_least`, all four operators, a null anchor, a null current value, the entry bar
  itself (change 0), long and short; the incremental advance equals the eager timeline bar for bar.
- Gate: `make verify` (ruff, mypy, full suite), `openspec validate research-entry-anchored-change-v1 --strict`.
