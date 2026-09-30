## 1. Contract (paths)

- [x] 1.1 Add `ManagedTransitionThresholdDTO`, `ManagedTransitionTermDTO`,
      `ManagedTransitionAtLeastDTO` and `ManagedTransitionPathDTO` to
      `domain/contracts.py`, all `frozen`, `extra="forbid"` (design D1).
- [x] 1.2 Add `paths` to `ManagedPhaseTransitionRuleDTO` with a
      three-way XOR validator.
- [x] 1.3 Validate referential integrity of all
      `condition_id`/`distance_id` references in
      `HistoricalManagedProjectionDTO`.
- [x] 1.4 Tests: composite rule decodes; atomic rule unchanged; XOR
      violations fail; a parametrized dangling-reference test covers
      every reference kind: atomic `condition_id`, atomic
      `distance_id`, path `condition_id`, path threshold `distance_id`,
      `at_least` condition term, `at_least` distance term, stop
      `distance_id`, runtime `condition_id`.

## 2. Consumer (paths, stop attribution)

- [x] 2.1 Add a shared `_phase_rule_met` returning `(met, path_id)`,
      used by `advance_managed_trade_state` and
      `build_managed_policy_timeline_from_projection` (design D2).
- [x] 2.2 Stop attribution mirrors `managed.py`: update price and rule
      id only on a change of more than `1e-8`, in both paths (design D3).
- [x] 2.3 Tests: first path wins; mixed market and trade; market-only
      and trade-only `at_least`; null threshold false; incremental
      equals eager on a paths corpus; stop rule id stable when not
      tightened.

## 3. Gating and local events

- [x] 3.1 `_open_managed_state` returns `(None, None)` first when no
      managed provider was supplied (design D4).
- [x] 3.2 `advance_managed_trade_state` appends per-bar events to an
      optional `event_sink` (design D5); `run_projection_execution_loop`
      passes `managed_event_sink` through;
      `MaterializeBacktestProjectionOutcome` supplies its
      `managed_policy_events` list.
- [x] 3.3 Tests: managed disabled with a managed projection means no
      managed candidates; event sequence for phase (with `path_id`),
      stop, take and runtime on a hand-computed trace; persisted trace
      non-empty on the projection path.

## 4. Gates (committed, operator-run)

- [x] 4.1 `scripts/managed_projection_parity.py` (design D6) with a
      counting Engine port wrapper and a JSON report.
- [x] 4.2 `scripts/managed_projection_benchmark.py` (design D7).
- [x] 4.3 Unit test the harness diff/report logic on synthetic results
      (no live services).
- [x] 4.4 Owner-run: parity on the atomic and composite candidates
      against Engine `07ff911`; PASS: atomic 287 trades and composite 276
      trades, zero failures, OLD/NEW managed-replay 287/0 and 277/0.
- [x] 4.5 Owner-run: benchmark on low/medium/high natural workloads.
      Low/medium completed three paired OLD/NEW repeats and passed; high NEW
      completed, while OLD was intentionally recorded as lower bounds
      (>6000 s atomic, >1800 s composite) at the owner's instruction.

## 5. Merge

- [ ] 5.1 `make verify` green (ruff, mypy, pytest).
- [ ] 5.2 On the owner's command: PR from this branch to `main`, merge,
      then sync specs and archive this change.
