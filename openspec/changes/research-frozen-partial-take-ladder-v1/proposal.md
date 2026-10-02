## Why

Strategy Engine now publishes a frozen partial take ladder on every
executable entry opportunity: Engine OpenSpec
`frozen-partial-take-ladder-v1`, implementation baseline `a4c3b02` on
strategy_engine branch `claude/project-thread-b1tmxk`.
- Each leg is `{take_id, ratio, fraction_of_initial, attribution}`.
- The legs are omitted when empty.
- A leg closes `fraction_of_initial` of the initial quantity at a level
  frozen at entry, and the existing final take closes all remaining
  exposure.

Research cannot execute this today. A position closes exactly once,
through one arbitration winner. `PositionExecution` has one `ExitFill`,
and `TradeRecord` assumes one exit price for the whole quantity. Its
strict decoder also rejects any opportunity that carries
`partial_takes`. This is stage 2 of the master plan
(`partial-take-profit/v1-frozen-partial-take-ladder-design.md`, §6–§8).

## What Changes

**Decode the ladder.** `ExecutableEntryOpportunityDTO` accepts an
optional `partial_takes` and validates it fail-closed:
- positive finite ratio;
- `0 < fraction_of_initial < 1`, and the fractions sum below 1;
- unique `take_id`, with `take_id == attribution.rule_id`;
- attribution `exit_kind` is `"partial_take"`.

`"partial_take"` is accepted only inside `partial_takes`.

**Freeze absolute leg levels at entry.**
- Each leg level is `anchor × (1 ± ratio)`, the same anchor and formula
  as the final take.
- Each leg quantity is `fraction_of_initial × Q0`, with Q0 the entry
  fill quantity. It is not rounded.
- Levels are stored on `InitialProtection` and never recalculated.

**Same-bar execution, from bar `entry + 1`:**
1. If the stop or the managed stop is touched, the existing arbitration
   runs unchanged. The stop closes all remaining exposure, and no take
   level is traversed.
2. Otherwise, the touched take levels are traversed in price order away
   from entry:
   - the touched levels are the unfilled legs plus the final take when
     it is active and touched;
   - a leg reduces the position at exactly its level and the traversal
     continues;
   - the final take closes the remainder through the existing
     `take_profit` candidate and stops the traversal;
   - at an equal level, a leg comes before the final take.
3. If the final take is not reached, the remainder goes through the
   existing runtime and signal arbitration.

Each leg fills at most once. `disable_initial_tp` suppresses only the
final take.

**One level-fill model for every resting exit.** V1 assumes a
continuous crypto-futures market. The initial stop, the managed stop,
each partial take and the final take fill at exactly their frozen level.
A bar that opens beyond a level no longer fills at the open: a long
final take at 108 with open 112 fills at 108, and a long stop at 95
with open 90 fills at 95. Short is the mirror. This replaces the
BBB/vectorbt fill-at-open rule in `_distance_fill_price` and
`_managed_stop_fill`, and applies to every run, with or without legs.

**Multi-fill position facts.**
- New: `PositionReduction` and `PositionExecution.reductions`.
- Remaining quantity is derived as `Q0 − Σ reductions` and is never
  stored.
- `ExitFill` stays the closing fill of the remainder.
- New execution event `position_reduced`.

**Aggregated accounting of one strategic trade.** One position is still
one `TradeRecord`:
- gross PnL and exit fees are summed over every fill;
- `exit_price` is the closing fill;
- `average_exit_price` and an `exit_fills` ledger are added;
- R keeps its denominator `Q0 × |entry − initial stop|`;
- capture and giveback use the average exit price;
- equity changes once, at the close, by the trade's net PnL.

A position left open at range end with filled legs is not a trade, as
today. Its reductions stay visible in `execution_events.json`.

**Byte-identical without legs on a continuous market.** For specs
without partial takes, on market data where no bar opens beyond an
active stop or final take level, these artifacts are byte-identical to
the output before this change: `strategy_evaluation.json`,
`trades.json`, `execution_events.json` and `metrics.json`.
`result.json` differs only by `run_id`. Empty ladder fields are
omitted, not written as `[]` or `null`. On a gap-through bar the stop
or final fill moves from the open to the level; that follows from the
accepted execution model and is not a regression.

**BREAKING:** stop, managed-stop and final-take fill prices change on
gap-through bars for all runs. No wire or artifact schema breaks.

## Non-Goals

- Strategy Runtime, the ABI executor and live trading. These are later
  master-plan stages, and live blockers B1/B2/B3/C1/C2 stay open.
- The historical E2E proof against the real Engine on a corpus. That is
  the next stage. This change provides the unit truth table and the
  no-legs regression gate only.
- Gap or slippage modelling of any kind.
- Signal-driven partial exits, market reductions, scale-in, or legs
  depending on managed phases.
- A Research-side quantity step or lot rounding.
- The legacy dense execution loop (`execution/loop.py`). It consumes no
  projection, so it never sees legs.
- research_frontend display of reductions.

## Capabilities

### New Capabilities
- `research-partial-take-execution-v1`: decoding the ladder, frozen
  leg levels and quantities, the same-bar rule (stop wins, then
  price-ordered traversal with a terminal final take, then runtime and
  signal), reduction facts and events, and positions left open with
  reductions.

### Modified Capabilities
- `research-unified-execution-loop-v1`: position cardinality now allows
  partial exits through the frozen ladder only.
- `research-trade-accounting-v1`:
  - gross PnL and exit fees over every fill of a position;
  - the multi-fill trade record;
  - R measured on the initial quantity;
  - capture metrics on the average exit price.
- `research-run-artifacts-v1`: ladder content in the persisted artifacts,
  and byte-identical artifacts without legs on a continuous market.
- `research-static-exit-arbitration-v1`: stop and take fill at exactly
  their level, with no fill at the open.
- `research-managed-policy-consumption-v1`: the managed stop fills at
  exactly its level, with no fill at the open.

## Impact

- `domain/contracts.py`:
  - `PartialTakeLegDTO`;
  - `ExecutableEntryOpportunityDTO.partial_takes`, omitted on dump when
    empty;
  - `ExitAttributionDTO.exit_kind` extended.
- `domain/execution.py`:
  - `ResolvedPartialTake`;
  - `InitialProtection.partial_takes`;
  - `PositionReduction`;
  - `PositionExecution.reductions`;
  - event type `position_reduced`.
- `execution/projection_entry.py`: resolves leg levels.
- New `execution/partial_takes.py`: the traversal.
- `execution/projection_loop.py`: a reduction phase before the existing
  arbitration, with stop-touched detection reusing the collected
  candidates.
- `accounting/contracts.py`, `accounting/service.py`: `TradeExitFill`,
  `TradeRecord.exit_fills` and `average_exit_price` (omitted when
  empty), and multi-fill arithmetic.
- `application/backtests/persist_run.py` and `read_artifacts.py`:
  omit-when-empty dumps, and old artifacts still read.
- `execution/static_exits._distance_fill_price` and
  `execution/managed_policy._managed_stop_fill`: the fill-at-open
  branches are removed. The existing gap tests are rewritten to the
  level fill.
- Unchanged:
  - `unified_exits.py` priorities;
  - managed policy decisions and its projection consumer;
  - sizing, batch summaries (they work from `net_pnl` and R).
- No dependency changes and no contract version bump.
