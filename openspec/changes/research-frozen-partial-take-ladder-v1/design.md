## Context

See proposal.md (Why). The source of truth for semantics is the accepted
master plan `partial-take-profit/v1-frozen-partial-take-ladder-design.md`
(§6 Research execution, §7 truth table, §8 accounting), together with the
Engine contract at strategy_engine `a4c3b02`:

- `ExecutableEntryOpportunity.partial_takes` holds the legs of `always_on`
  plus the locked profile, ratio ascending. Each leg is `{take_id, ratio:
  float, fraction_of_initial: float, attribution{rule_id = take_id,
  component_id, exit_kind: "partial_take"}}`.
- The key is absent when there are no legs, and the version stays
  `strategy_evaluation_execution.v2`.

Today in research_service (main 7a07ca5):

- Single runs and batches both execute through
  `MaterializeBacktestProjectionOutcome` → `run_projection_execution_loop`
  (`execution/projection_loop.py`). Closed positions are accounted
  immediately by `closed_position_consumer`, against a running equity.
- Per bar, for a position open at bar start, the loop does the
  following:
  1. collects static candidates (`projection_static_exits.py`: stop/take
     through `_distance_fill_price`, plus a locked-profile signal);
  2. collects managed candidates;
  3. `arbitrate_unified_exit_candidates` picks one winner by priority:
     `stop_loss 1 < managed_stop 2 < take_profit 3 < runtime 4–6 <
     signal 7`;
  4. the winner becomes the single `ExitFill` and the position closes.
- `InitialProtection` holds the frozen stop/take prices
  (`anchor × (1 ± ratio)`, anchor = signal-bar close).
- Stop, take and managed stop currently fill at the bar open when the
  open is already beyond the level (`static_exits._distance_fill_price`,
  `managed_policy._managed_stop_fill`). This mirrors BBB/vectorbt gap
  semantics and contradicts the master plan's continuous-market model.
- `TradeRecord` assumes one exit price for `quantity`, and its
  validator checks fee/net/equity/R arithmetic.
- Persistence writes `model_dump(mode="json")` of
  `HistoricalExecutionProjectionDTO`, `TradeRecord` and `ExecutionEvent`,
  with `sort_keys`. A new field with a default would therefore appear
  in every artifact.

## Goals / Non-Goals

**Goals:**
- Execute the ladder deterministically on the projection loop, with
  the smallest structural change: a reduction phase before the existing,
  untouched arbitration.
- One strategic position stays one trade.
- One execution model for every resting exit order: stop, managed stop,
  partial take and final take each fill at exactly their level.
- Output without legs stays byte-identical on market data without
  gap-through bars.

**Non-Goals:**
- Changing arbitration priorities, managed policy decisions, sizing or
  batch summaries.
- Gap or slippage modelling of any kind.
- Runtime, executor or live concerns.

## Decisions

### D1. A reduction phase before the existing arbitration

The loop keeps collecting static and managed candidates exactly as
today. Then:

1. If any candidate is `stop_loss` or `managed_stop`, nothing new
   happens. The existing arbitration runs, and the stop wins and closes
   the remainder.
2. Otherwise, `traverse_partial_takes(position, candle, filled_ids,
   final_level)` returns this bar's reductions:
   - `final_level` is the `reference_level` of the `take_profit`
     candidate when one exists (active and touched), else `None`;
   - touched legs are filtered and sorted by distance from the anchor,
     ties in wire order;
   - legs strictly beyond `final_level` are dropped, and a leg at the
     same level is kept.
3. The existing arbitration then runs on the same candidates:
   - when the final take was touched, its `take_profit` candidate
     outranks runtime and signal (priority 3), so it closes the
     remainder; this is the terminal final take;
   - otherwise runtime and signal arbitrate the remainder as before.

Why: the same-bar rule is enforced by the existing priority table, and
nothing in arbitration changes.

Alternative considered: a fill-quantity field on `ExitCandidate`, and
arbitration that returns several winners. This was rejected because it
changes the winner contract for every caller.

### D2. Position model: frozen ladder plus derived remainder

- `InitialProtection.partial_takes: tuple[ResolvedPartialTake, ...] =
  ()`. Each entry holds `take_id`, `level`, `fraction_of_initial`,
  `quantity` and attribution, and is resolved once in
  `resolve_initial_protection_from_opportunity`.
  - Formula: `anchor × (1 ± Decimal(str(ratio)))`, the same as the
    final take.
  - `quantity = Decimal(str(fraction)) × entry_fill.quantity`, with no
    rounding.
- `PositionReduction` (frozen) holds `fill_id = reduce:{position_id}:
  {take_id}`, the bar, time, level, fill price (= level), quantity,
  fraction and attribution.
- `PositionExecution.reductions: tuple[PositionReduction, ...] = ()`.
  The closing `exit_fill` keeps its meaning.
- The loop keeps the reductions of the open position in a local list,
  and builds the filled-id set from it.
- There is no `remaining_quantity` field. The remaining quantity is
  `Q0 − Σ reductions`, computed where needed: the event metadata and the
  accounting.
- `PositionState` stays frozen and unchanged.

### D3. Decoding is strict and fail-closed

New `PartialTakeLegDTO` (`extra="forbid"`).
`ExecutableEntryOpportunityDTO.partial_takes` defaults to `()` and
validates:
- the ratio is finite and > 0;
- each fraction is in (0, 1) and the fractions sum below 1;
- `take_id`s are unique, and each `take_id` equals `attribution.rule_id`;
- the leg's `exit_kind` is `partial_take`.

`ExitAttributionDTO.exit_kind` widens to include `"partial_take"`. The
existing leg validators keep `initial_stop` and `initial_take` at
`stop_loss` and `take_profit`, and signal candidates at `signal`, so
the new value is legal only inside legs.

Research does not trust Engine's ordering for execution: it sorts by
level. Wire order is used only to break ties.

### D4. Omit-when-empty serialization

A `model_serializer(mode="wrap")` drops `partial_takes` when it is
empty on `ExecutableEntryOpportunityDTO`. The same applies to
`exit_fills` and `average_exit_price` on `TradeRecord`. Event metadata
is built conditionally: `entry_filled` gets `partial_takes` only when
legs exist.

As a result, `strategy_evaluation.json`, `trades.json` and
`execution_events.json` are byte-identical without legs, subject to D8:
a bar that opens beyond a stop or final level changes its fill price by
design. Reading old
artifacts still works through defaults.

Alternative considered: `Field(exclude_if=…)`. It was rejected because
it needs pydantic ≥ 2.11, while the floor is 2.8.

### D5. Accounting of one strategic trade

`account_closed_execution` builds fills from `reductions` plus the
closing fill, whose quantity is `Q0 − Σ reductions`.

| Quantity | Rule |
|---|---|
| `gross` | `Σ side-aware (p_i − entry) × q_i` |
| `exit_notional` | `Σ p_i × q_i` |
| `exit_fee` | `Σ p_i × q_i × rate` |
| `quantity` | Q0 |
| `exit_price` | the closing fill |
| `average_exit_price` | `exit_notional / Q0` |
| R | unchanged formula over Q0 and total PnL |

The R validator (`initial_risk_amount == initial_risk_price × quantity`)
stays true. Capture and giveback use `average_exit_price`, and MFE/MAE
keep the window from entry through the closing bar.

- `TradeExitFill` holds kind `partial_take|final`, `take_id`, bar, time,
  price, quantity, notional, fee and attribution.
- `exit_fills` is filled only when reductions exist. A single-fill trade
  keeps `()`, so its record stays identical.
- The validator checks the sums of quantity, fee and notional when
  `exit_fills` is non-empty.
- Equity changes once, at the close. The equity chain is unchanged
  because positions never overlap.

### D6. Events

`position_reduced` is appended to `ExecutionEvent.event_type`.
- `event_id = event:reduce:{position_id}:{take_id}`.
- Metadata: `take_id`, `level`, `fill_price`, `quantity`,
  `fraction_of_initial`, `remaining_quantity`, `rule_id`,
  `component_id`, `exit_kind`, `locked_exit_profile`.
- Order within a bar: reductions in traversal order, then `exit_filled`.

`exit_filled` metadata is unchanged.

### D7. Open at range end with reductions (master plan D5)

The position stays `open`. Its `PositionExecution(status="open")`
carries the reductions, and its events show them. There is no trade and
no equity update, which is consistent with "open positions reported, not
forced".

### D8. One level-fill model for resting exits (continuous market)

Owner decision: V1 assumes a continuous crypto-futures market. Every
resting exit order fills at exactly its frozen reference level, and a
bar that opens beyond a level does not fill at the open.

| Order | Touched when (long) | Touched when (short) | Fill |
|---|---|---|---|
| initial stop | `low ≤ level` | `high ≥ level` | level |
| managed stop | `low ≤ level` | `high ≥ level` | level |
| partial take | `high ≥ level` | `low ≤ level` | level |
| final take | `high ≥ level` | `low ≤ level` | level |

Examples: long final 108 with open 112 fills at 108, not 112. Long stop
95 with open 90 fills at 95, not 90. Short is the mirror.

Implementation:
- `static_exits._distance_fill_price` returns the level whenever the bar
  reached it, with the open branches removed. It is shared by the
  projection loop (`projection_static_exits.py`) and the legacy dense
  loop, so both follow the same model.
- `managed_policy._managed_stop_fill` gets the same change.
- The leg traversal uses the same touch test.
- Arbitration, candidate collection and priorities are unchanged; only
  the fill price on a gap-through bar changes.

This modifies two existing requirements: `research-static-exit-arbitration-v1`
"Distance fill semantics" and `research-managed-policy-consumption-v1`
"Managed stop execution". The existing gap tests
(`test_static_exit_arbitration.py` 73/81/89,
`test_managed_policy_consumption.py` 156) are rewritten to the level
fill. Parity with BBB/vectorbt is deliberately not kept on gap-through
bars; on bars without a gap-through the fill is the same as before.

### D9. Scope of the loop change

- Only `projection_loop.py` changes.
- The legacy dense loop (`execution/loop.py`) consumes no projection, so
  it cannot receive legs.
- Both managed paths (incremental projection, and the legacy
  `/managed-replay` oracle) feed candidates into the same D1 phase.
  Managed state advances from prices only, so reductions do not affect
  it.

## Risks / Trade-offs

- [Byte drift for existing runs through new defaulted fields] → D4
  serializers. A regression gate re-runs recorded no-leg fixtures
  without gap-through bars and compares sha256 values.
- [Gap-through bars change stop/final fills for existing specs] →
  Accepted by D8 and not a regression. A separate test pins the new
  fill on synthetic gap-through bars.
- [Float ratio and fraction converted to Decimal] → `Decimal(str(x))`
  (shortest repr) for both, the same convention as the existing ratios.
- [Realised leg PnL of an open-at-end position is not in equity] → This
  is accepted by the master plan (D5) and stays visible in events. It
  can be revisited at the proof stage.
- [CPU] → Without legs the per-bar cost is one empty-tuple check. With
  legs it is O(legs) per bar of an open position.

## Migration Plan

- Deploy Research before any Engine spec with legs is used. Engine and
  Research are compatible in both orders for specs without legs.
- Rollback: revert Research. Artifacts written with legs would then be
  read by an older reader, which rejects unknown keys only on decode of
  new projections; already persisted runs are not re-decoded by the
  executor.
