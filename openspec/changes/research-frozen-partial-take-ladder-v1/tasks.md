Each group ends green. The no-legs gate from group 0 runs again at the
end of every group, and it is never re-recorded.

## 0. Baseline gate for specs without legs

- [ ] 0.1 Before any code change, on main `7a07ca5`, record a no-legs
      regression fixture:
      - a recorded Engine projection without `partial_takes`, both
        sides, with stop, final take, a runtime exit, a signal exit and
        a position left open;
      - the sha256 of `strategy_evaluation.json`, `trades.json`,
        `execution_events.json` and `metrics.json` produced by the
        existing single-run path through `persist_run`;
      - `result.json` compared after removing `run_id`.

      No live Engine and no market data load: the fixture is a local
      file. Verify: the new gate test is green on unchanged code.
- [ ] 0.2 The gate names the requirement it protects
      (`research-run-artifacts-v1` "Byte-identical artifacts without
      partial takes"). Verify: the test id or message cites it.

## 1. Decoding the ladder

- [ ] 1.1 `domain/contracts.py`:
      - add `PartialTakeLegDTO` (`extra="forbid"`);
      - add `ExecutableEntryOpportunityDTO.partial_takes = ()`;
      - widen `ExitAttributionDTO.exit_kind` with `"partial_take"`;
      - validate per design D3.

      Verify: tests in `test_historical_execution_projection_contract.py`
      cover acceptance of a valid ladder, absence of the key, and one
      rejection per rule (non-finite or non-positive ratio, fraction
      outside (0, 1), sum ≥ 1, duplicate `take_id`, `take_id` ≠
      `rule_id`, wrong leg kind, `partial_take` on `initial_take`,
      `initial_stop` or a signal).
- [ ] 1.2 Omit-when-empty serializer on `ExecutableEntryOpportunityDTO`
      (design D4). Verify: a dump without legs has the same key set as
      before, and a dump with legs reproduces the Engine scenario JSON
      at `a4c3b02` exactly.
- [ ] 1.3 Run the group 0 gate. Verify: green.

## 2. Frozen leg levels on the position

- [ ] 2.1 `domain/execution.py`: add `ResolvedPartialTake` and
      `InitialProtection.partial_takes = ()`.
      `projection_entry.resolve_initial_protection_from_opportunity`
      resolves levels `anchor × (1 ± ratio)` and quantities
      `fraction × Q0` (design D2). A non-positive level fails closed.

      Verify: tests in `test_initial_protection.py` cover:
      - long 101 with quantity 25;
      - the short mirror;
      - a leg beyond the final take, stored without comparison;
      - a non-positive short leg rejected;
      - unchanged protection without legs.
- [ ] 2.2 Run the group 0 gate. Verify: green.

## 3. Traversal and the loop reduction phase

- [ ] 3.1 New `execution/partial_takes.py` with a pure
      `traverse_partial_takes` (design D1). It takes the resolved legs,
      the filled ids, the side, the candle and the final level (or
      `None`), and returns the ordered reductions.

      Verify: unit tests in a new `test_partial_take_traversal.py`
      cover:
      - nearest-first order;
      - a leg beyond the final take dropped;
      - a leg at the final level kept and placed first;
      - equal leg levels in wire order;
      - already-filled legs skipped;
      - fill at the exact level when the bar opens beyond it;
      - the short mirror.
- [ ] 3.2 `execution/projection_loop.py`: add the reduction phase before
      the unchanged arbitration:
      - no traversal when a `stop_loss` or `managed_stop` candidate
        exists;
      - no traversal on the entry bar;
      - the final level comes from the `take_profit` candidate;
      - `PositionReduction`s are kept in the loop and attached to
        `PositionExecution.reductions`;
      - the closing fill carries the remaining quantity.

      Verify: loop tests in a new `test_partial_take_execution.py`
      cover every scenario of `research-partial-take-execution-v1`,
      including:
      - stop and legs on one bar;
      - legs then final on one bar;
      - a leg beyond the final take never fills;
      - the short mirror;
      - a leg at the final level;
      - a leg and a signal exit on one bar;
      - a leg earlier and the stop later;
      - the entry bar reaching every level;
      - `disable_initial_tp` with legs;
      - a managed stop on a bar that touches a leg.
- [ ] 3.3 Cover the master plan §7 truth table rows 1–16 as
      parametrised cases in `test_partial_take_execution.py`. Verify:
      every row passes, and a row comment cites its number.
- [ ] 3.4 Run the group 0 gate plus `test_unified_execution_loop.py`,
      `test_static_exit_arbitration.py`, `test_unified_exit_arbitration.py`
      and the managed policy tests. Verify: green without changes to
      those tests.

## 4. Events

- [ ] 4.1 Add the `position_reduced` event type (design D6). Emit it
      per reduction, before the same bar's `exit_filled`. `entry_filled`
      metadata lists the resolved legs only when legs exist.

      Verify: tests in `test_partial_take_execution.py` cover:
      - event order for a leg and the final take on one bar;
      - the metadata keys and the `remaining_quantity` values;
      - `event_id` format;
      - `entry_filled` metadata without legs unchanged.
- [ ] 4.2 Open position at range end with reductions (design D7).
      Verify: a test shows `position_reduced` plus `position_left_open`
      events and no trade record.
- [ ] 4.3 Run the group 0 gate. Verify: green.

## 5. Accounting of one strategic trade

- [ ] 5.1 `accounting/contracts.py`: add `TradeExitFill`,
      `TradeRecord.exit_fills = ()` and `average_exit_price`, both
      omitted when empty, with sum validators on quantity, notional and
      fee (design D5).

      Verify: contract tests in `test_trade_accounting.py` cover:
      - a valid multi-fill record;
      - a rejection per broken sum;
      - a single-fill record dumping exactly as before.
- [ ] 5.2 `accounting/service.account_closed_execution` builds fills
      from the reductions plus the closing fill:
      - gross PnL and exit fee summed per fill;
      - `exit_price` is the closing fill;
      - `average_exit_price` is `Σ p·q / Q0`;
      - R stays over Q0;
      - capture and giveback use the average exit price;
      - equity is updated once.

      Verify: tests in `test_trade_accounting.py` and
      `test_trade_native_r_accounting.py` reproduce the spec examples
      (gross 500, average exit 105), check fees per fill, and check R
      with a stop after a leg.
- [ ] 5.3 Run the group 0 gate plus the existing accounting and sizing
      tests. Verify: green without changes to existing tests.

## 6. Persistence and reading

- [ ] 6.1 `persist_run.py` and `read_artifacts.py` write and read ladder
      content: opportunities with legs, trades with `exit_fills`, and
      `position_reduced` events. Old artifacts still read through
      defaults.

      Verify: tests in `test_run_artifacts.py` cover a round trip with
      legs and reading an artifact recorded before this change.
- [ ] 6.2 Run the group 0 gate. Verify: green with no re-recording.

## 7. Integration checks

- [ ] 7.1 End-to-end single run and batch through
      `MaterializeBacktestProjectionOutcome` on a recorded projection
      with one pct and one ATR leg in `always_on` plus one leg in a
      locked profile. Use a local fixture with no live Engine. Verify:
      - the trades, events and metrics match hand-computed values;
      - the batch summary equals the sum of single-run trades.
- [ ] 7.2 Run `make verify` and `openspec validate
      research-frozen-partial-take-ladder-v1 --strict`. Verify: all
      green.
