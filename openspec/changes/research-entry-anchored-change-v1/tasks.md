## 1. Contract

- [ ] 1.1 `ManagedTransitionEntryChangeDTO {series_id, op, value}` (`op` closed enum, finite `value`);
      `ManagedTransitionPathDTO.entry_changes` (default empty) and `ManagedTransitionTermDTO.entry_change` (exactly one
      variant per term). Reference validation covers every `series_id`. Verify: decode tests for acceptance, each
      rejection, and an unchanged decode of a projection without the new fields.

## 2. Execution

- [ ] 2.1 `_path_met` evaluates entry changes against the position's entry bar index; `_phase_rule_met` and both call sites
      (eager timeline, incremental advance) pass it. Verify: tests for `require` and `at_least`, all four operators, null
      anchor, null current value, the entry bar itself, both sides.
- [ ] 2.2 Incremental advance equals the eager timeline bar for bar on a projection with entry changes. Verify: test.

## 3. Gate

- [ ] 3.1 `make verify` is green.
- [ ] 3.2 `openspec validate research-entry-anchored-change-v1 --strict` passes.
